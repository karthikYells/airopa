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
from app.signals import sector_cache
from app.signals.sector import classify_sector

_TTL = 90 * 86400
_MAX_PEERS = 15
_MIN_KNOWN = 5          # publish a count only over at least this many known peers


def _fresh(doc: dict | None) -> bool:
    return bool(doc) and time.time() - doc.get("fetched_at", 0) < _TTL


def _headers(settings: Settings) -> dict:
    return {"X-Api-Key": settings.apollo_api_key, "Cache-Control": "no-cache",
            "Content-Type": "application/json"}


# Industry codes (NAICS 2017, four digits) per sector key: a fixed table we own,
# used with the prospect's own Apollo codes. Codes are far tighter than
# Apollo's keyword tags, which returned fashion houses for a valve maker.
SECTOR_NAICS = {
    "automotive_components": ["3363"],
    "industrial_machinery": ["3331", "3332", "3333", "3339"],
    "precision_components": ["3329", "3327", "3336"],
    "electronics_hardware": ["3341", "3342", "3344", "3345"],
    "medical_devices": ["3391", "3345"],
    "pharma_chemicals": ["3254", "3251", "3252", "3255", "3259"],
    "software_saas": ["5112", "5182", "5415"],
    "industrial_automation": ["3345", "3353", "3339"],
    "building_construction": ["2362", "2371", "2382", "3273", "3323"],
    "logistics_distribution": ["4931", "4841", "4885", "4238"],
    "consumer_goods": ["3352", "3399", "3256", "3371", "3162"],
    "energy_utilities": ["2211", "2212", "2111"],
    "financial_services": ["5221", "5231", "5241"],
    "professional_services": ["5416", "5413", "5419"],
    "food_beverage": ["3119", "3114", "3115", "3121"],
    "aerospace_defence": ["3364"],
    "textiles": ["3131", "3132", "3133", "3152"],
}


# Sectors close enough to count as peers of each other. A valve maker's peers
# include machinery and automation companies; a fashion house never is one.
_FAMILIES = [
    {"precision_components", "industrial_machinery", "industrial_automation", "automotive_components"},
    {"electronics_hardware", "industrial_automation", "medical_devices"},
    {"medical_devices", "pharma_chemicals"},
    {"software_saas", "professional_services", "financial_services"},
    {"building_construction"}, {"logistics_distribution"}, {"consumer_goods", "textiles"},
    {"energy_utilities"}, {"food_beverage"}, {"aerospace_defence"},
]


def same_family(a: str | None, b: str | None) -> bool:
    return bool(a and b) and (a == b or any(a in f and b in f for f in _FAMILIES))


def peer_filters(ap: ApolloResult, sector_key: str | None = None) -> dict | None:
    """Search filters from the prospect's own Apollo record and its sector. None
    when there is nothing to match an industry on: the cohort is never guessed."""
    body: dict = {"organization_locations": ["Europe"], "per_page": 40, "page": 1}
    codes = sorted({c[:4] for c in ap.naics_codes if len(c) >= 4} | set(SECTOR_NAICS.get(sector_key or "", [])))
    if codes:
        body["organization_naics_codes"] = codes
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
    return out


def discover(ap: ApolloResult, settings: Settings, sector_key: str | None = None) -> dict | None:
    """The prospect's peer set, from the store or one Apollo company search.
    A stored search made with different filters is redone."""
    body = peer_filters(ap, sector_key)
    cached = kv.get("cohorts", ap.domain)
    if _fresh(cached) and cached.get("filters") == body:
        return cached
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


def peer_sector(peer: dict, llm=None) -> str | None:
    """The peer's sector key, decided the same way as the prospect's: from its
    own homepage. Saved per domain so a peer is classified once."""
    from app.adapters.web_scraper import _text

    key = sector_cache.get(peer["domain"])
    if key:
        return key
    try:
        r = httpx.get(f"https://{peer['domain']}", timeout=httpx.Timeout(8.0, connect=4.0), follow_redirects=True,
                      headers={"User-Agent": "AiropaBot/1.0 (+https://airopa.co)"})
        text = _text(r.text)[:3000] if r.status_code < 400 else ""
    except Exception:
        return None
    key, _, method = classify_sector(text, llm=llm, name=peer.get("name"))
    if key and method == "model":
        sector_cache.put(peer["domain"], key)
    return key


def _band(rev_eur: float | None) -> str:
    if not rev_eur:
        return ""
    lo, hi = rev_eur / 3, rev_eur * 3

    def fmt(v):
        return f"{v / 1e9:.0f}bn" if v >= 1e9 else f"{math.floor(v / 1e8) * 100:.0f}m"
    return f", EUR {fmt(lo)} to {fmt(hi)} revenue"


def build_cohort(ap: ApolloResult, sector: str | None, settings: Settings, llm=None,
                 sector_key: str | None = None) -> dict | None:
    """The cohort with every peer checked, plus the derived metrics (PEER.30).
    A candidate from the company search is a peer only if its own homepage puts
    it in the prospect's sector: the search's industry match alone is too loose
    (it returned fashion houses for a components maker)."""
    found = discover(ap, settings, sector_key)
    if not found or not found.get("peers"):
        return None
    candidates = found["peers"]
    if sector_key:
        with ThreadPoolExecutor(max_workers=8) as pool:
            keys = list(pool.map(lambda p: peer_sector(p, llm), candidates))
        # Keep: same sector family, or homepage unreadable (the industry codes
        # already matched). Drop: the peer's own homepage says another family.
        # Closest first: same sector, then unreadable homepage, then the wider family.
        rank = {True: 0, None: 1, False: 2}
        kept = [(rank[k == sector_key if k else None], i, p) for i, (p, k) in enumerate(zip(candidates, keys))
                if k is None or same_family(k, sector_key)]
        candidates = [p for _, _, p in sorted(kept, key=lambda x: (x[0], x[1]))]
    candidates = candidates[:_MAX_PEERS]
    if not candidates:
        return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        checked = list(pool.map(lambda p: check_peer(p, settings, llm), candidates))
    known = [p for p in checked if p["status"] in ("yes", "no")]
    with_centre = [p for p in known if p["status"] == "yes"]
    return {
        "peers": checked,
        "known": len(known),
        "with_centre": len(with_centre),
        "aggregate_india_profiles": sum(p["india_profiles"] for p in with_centre),
        "definition": f"European {(sector or 'industrial').lower()} and related companies{_band(ap.revenue_eur)}",
        "publishable": len(known) >= _MIN_KNOWN,
        "credits_used": found.get("credits_used", 0),
    }


# --- background build ---------------------------------------------------------------
# Building a cohort reads up to 40 homepages and checks each peer, which takes
# minutes: far longer than a page visit may wait. A visit only reads a finished
# cohort; if there is none it queues the prospect, and the scheduled task
# (/api/tasks/build-cohorts) builds it. The next visit, or the PDF, shows it.

def cached_cohort(ap: ApolloResult, sector: str | None, sector_key: str | None) -> dict | None:
    done = kv.get("cohort_built", ap.domain)
    if _fresh(done):
        return done
    if kv.get("cohort_queue", ap.domain) is None:
        kv.put("cohort_queue", ap.domain, {"domain": ap.domain, "sector": sector,
                                           "sector_key": sector_key, "queued_at": time.time()})
    return None


def build_queued(settings: Settings, llm=None, budget_s: float = 700) -> list[dict]:
    """Build queued cohorts until the time budget runs out."""
    start, out = time.time(), []
    for domain in kv.keys("cohort_queue"):
        if time.time() - start > budget_s:
            break
        q = kv.get("cohort_queue", domain) or {}
        raw = kv.get("apollo", q.get("domain", domain))
        if raw is None:
            kv.delete("cohort_queue", domain)
            continue
        ap = ApolloResult(**raw)
        cohort = build_cohort(ap, q.get("sector"), settings, llm=llm, sector_key=q.get("sector_key"))
        kv.put("cohort_built", ap.domain, {**(cohort or {"empty": True}), "fetched_at": time.time()})
        kv.delete("cohort_queue", domain)
        out.append({"domain": ap.domain, "known": (cohort or {}).get("known", 0),
                    "with_centre": (cohort or {}).get("with_centre", 0)})
    return out
