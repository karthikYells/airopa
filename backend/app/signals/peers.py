"""Peer set and peer India penetration (Section 5.8, PEER.01 / PEER.10 / PEER.30).

The peer set is European companies in the same industry (Apollo industry
codes, or its industry tag when no code is known) and the same revenue band
(roughly a third to three times the prospect's revenue). Finding it is one
Apollo company search (1 credit, only when it returns results). Each peer's
India presence is then checked with Apollo's free people search and judged by
the same India gate the prospect gets: an India entity AND technology roles
is a verified centre. A peer Apollo knows too little about stays UNKNOWN and is
left out of the count, never scored as "no".

Both the cohort (per prospect) and each peer record (per peer domain) live in
the shared store (app.data.kv) for 90 days, as Section 5.8 requires: a peer
checked for one prospect is reused for the next.
"""
from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.adapters.apollo import _API, _TIMEOUT, _USD_TO_EUR, ApolloResult, normalise_domain, parse_people
from app.config import Settings
from app.data import kv
from app.data.records import GateVerdict
from app.gate.india_gate import run_gate
from app.gate.title_classifier import classify_titles

_TTL = 90 * 86400
_MAX_PEERS = 15
_MIN_KNOWN = 5          # publish a count only over at least this many known peers


def _fresh(doc: dict | None) -> bool:
    return bool(doc) and time.time() - doc.get("fetched_at", 0) < _TTL


def _headers(settings: Settings) -> dict:
    return {"X-Api-Key": settings.apollo_api_key, "Cache-Control": "no-cache",
            "Content-Type": "application/json"}


def peer_filters(ap: ApolloResult) -> dict | None:
    """Search filters from the prospect's own Apollo record. None when there is
    nothing to match an industry on: the cohort is never guessed."""
    body: dict = {"organization_locations": ["Europe"], "per_page": 40, "page": 1}
    if ap.naics_codes:
        body["organization_naics_codes"] = [ap.naics_codes[0][:4]]
    elif ap.sic_codes:
        body["organization_sic_codes"] = [ap.sic_codes[0][:4]]
    elif ap.industry:
        body["q_organization_keyword_tags"] = [ap.industry]
    else:
        return None
    if ap.revenue_eur:
        usd = ap.revenue_eur / _USD_TO_EUR
        body["revenue_range"] = {"min": int(usd / 3), "max": int(usd * 3)}
    elif ap.employees:
        body["organization_num_employees_ranges"] = [f"{max(1, ap.employees // 3)},{ap.employees * 3}"]
    else:
        return None
    return body


def parse_peers(data: dict, own_domain: str, own_name: str | None,
                own_industry: str | None = None) -> list[dict]:
    """Peers from a company search. A keyword match is loose (a CAD software
    house tagged "machinery"), so when both sides carry an Apollo industry,
    only the same industry counts as a peer."""
    out, seen = [], {own_domain}
    want = (own_industry or "").strip().lower()
    for o in (data.get("organizations") or []) + (data.get("accounts") or []):
        dom = normalise_domain(o.get("primary_domain") or o.get("domain") or "")
        name = (o.get("name") or "").strip()
        industry = (o.get("industry") or "").strip().lower()
        if not dom or dom in seen or (own_name and name.lower() == own_name.lower()):
            continue
        if want and industry and industry != want:
            continue
        seen.add(dom)
        out.append({"name": name, "domain": dom, "country": o.get("country"),
                    "industry": industry or None})
    return out[:_MAX_PEERS]


def discover(ap: ApolloResult, settings: Settings) -> dict | None:
    """The prospect's peer set, from the store or one Apollo company search."""
    cached = kv.get("cohorts", ap.domain)
    if _fresh(cached):
        return cached
    body = peer_filters(ap)
    if body is None or not settings.apollo_peer_search:
        return None
    try:
        with httpx.Client(timeout=_TIMEOUT, headers=_headers(settings)) as c:
            r = c.post(f"{_API}/mixed_companies/search", json=body)
            r.raise_for_status()
            peers = parse_peers(r.json(), ap.domain, ap.name, ap.industry)
    except Exception:
        return None
    doc = {"domain": ap.domain, "peers": peers, "filters": body, "fetched_at": time.time(),
           "credits_used": 1 if peers else 0}
    kv.put("cohorts", ap.domain, doc)
    return doc


def check_peer(peer: dict, settings: Settings, llm=None) -> dict:
    """PEER.10 / PEER.12 / PEER.13 for one peer: verified centre yes / no /
    unknown, India profile count and function mix. Free Apollo calls only."""
    from app.signals.collect import _gate_inputs_from_titles

    cached = kv.get("peers", peer["domain"])
    if _fresh(cached):
        return cached
    doc = {**peer, "status": "unknown", "india_profiles": 0, "mix": {}, "fetched_at": time.time()}
    try:
        with httpx.Client(timeout=_TIMEOUT, headers=_headers(settings)) as c:
            r = c.post(f"{_API}/mixed_people/api_search", params=[
                ("q_organization_domains_list[]", peer["domain"]), ("person_locations[]", "India"),
                ("per_page", 100), ("page", 1)])
            r.raise_for_status()
            india, titles = parse_people(r.json())
            r = c.post(f"{_API}/mixed_people/api_search", params=[
                ("q_organization_domains_list[]", peer["domain"]), ("per_page", 1), ("page", 1)])
            r.raise_for_status()
            total, _ = parse_people(r.json())
    except Exception:
        return doc   # not stored: try again next time
    doc["india_profiles"] = india
    if india == 0 and total < settings.apollo_min_profiles:
        kv.put("peers", peer["domain"], doc)   # Apollo barely knows them: unknown
        return doc
    classified = classify_titles(titles, llm=llm)
    gi = _gate_inputs_from_titles(
        entity_exists=india >= settings.apollo_india_entity_min, india_headcount=india,
        classified=classified, postings=0, announcement=False, parent_gcc=False, nic_codes=[],
        records=max(len(titles), 3) + 1, min_records_override=settings.gate_min_evidence_records_live)
    verdict = run_gate(gi, settings).verdict
    doc["status"] = ("yes" if verdict is GateVerdict.CONFIRMED
                     else "no" if verdict in (GateVerdict.CLEAR, GateVerdict.CLEAR_GREENFIELD)
                     else "unknown")
    mix: dict[str, int] = {}
    for t in classified:
        mix[t.title_class.value] = mix.get(t.title_class.value, 0) + 1
    doc["mix"] = mix
    kv.put("peers", peer["domain"], doc)
    return doc


def _band(rev_eur: float | None) -> str:
    if not rev_eur:
        return ""
    lo, hi = rev_eur / 3, rev_eur * 3

    def fmt(v):
        return f"{v / 1e9:.0f}bn" if v >= 1e9 else f"{math.floor(v / 1e8) * 100:.0f}m"
    return f", EUR {fmt(lo)} to {fmt(hi)} revenue"


def build_cohort(ap: ApolloResult, sector: str | None, settings: Settings, llm=None) -> dict | None:
    """The cohort with every peer checked, plus the derived metrics (PEER.30)."""
    found = discover(ap, settings)
    if not found or not found.get("peers"):
        return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        checked = list(pool.map(lambda p: check_peer(p, settings, llm), found["peers"]))
    known = [p for p in checked if p["status"] in ("yes", "no")]
    with_centre = [p for p in known if p["status"] == "yes"]
    return {
        "peers": checked,
        "known": len(known),
        "with_centre": len(with_centre),
        "aggregate_india_profiles": sum(p["india_profiles"] for p in with_centre),
        "definition": f"European {(sector or 'industry').lower()} companies{_band(ap.revenue_eur)}",
        "publishable": len(known) >= _MIN_KNOWN,
        "credits_used": found.get("credits_used", 0),
    }
