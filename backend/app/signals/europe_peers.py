"""Indian peers already in Europe (PEER cluster, Europe Market Assessment).

Peers: Indian companies with the same industry codes (NAICS, from the
prospect's own Apollo record) and a revenue band of a third to three times
theirs. One Apollo company search (1 credit, only when it returns results).
No keyword matching: a company without industry codes gets no peer headline,
because loose keyword peers proved unreliable on the India engine.

Each peer's Europe presence comes from the free people search: 10 or more
Europe-based people is "yes", fewer than 3 with a well-covered company is
"no", anything else is unknown and left out of the count.
Cohorts and peer records are kept in the shared store for 90 days.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.adapters.apollo import _API, _TIMEOUT, _USD_TO_EUR, normalise_domain
from app.config import Settings
from app.data import kv
from app.signals.europe_presence import _count
from app.signals.peers import parse_peers

_TTL = 90 * 86400
_MAX = 12
_MIN_KNOWN = 5
_EUROPE = ["European Union", "United Kingdom", "Switzerland", "Norway"]


def _fresh(doc):
    return bool(doc) and time.time() - doc.get("fetched_at", 0) < _TTL


def filters(org: dict) -> dict | None:
    codes = sorted({c[:4] for c in (org.get("naics_codes") or []) if len(c) >= 4})
    if not codes:
        return None
    body = {"organization_locations": ["India"], "organization_naics_codes": codes, "per_page": 30, "page": 1}
    if org.get("revenue_eur"):
        usd = org["revenue_eur"] / _USD_TO_EUR
        body["revenue_range"] = {"min": int(usd / 3), "max": int(usd * 3)}
    elif org.get("employees"):
        e = org["employees"]
        body["organization_num_employees_ranges"] = [f"{max(1, e // 3)},{e * 3}"]
    else:
        return None
    return body


def _headers(settings):
    return {"X-Api-Key": settings.apollo_api_key, "Cache-Control": "no-cache", "Content-Type": "application/json"}


def _recent_europe(c, domain: str) -> int:
    """Europe-based people who started their current role in the last 12
    months (free search): how fast a peer is building in Europe."""
    from app.adapters.apollo import parse_people
    body = {"q_organization_domains_list": [domain], "person_locations": _EUROPE,
            "person_days_in_current_title_range": {"max": 365}, "per_page": 1, "page": 1}
    r = c.post(f"{_API}/mixed_people/api_search", json=body)
    r.raise_for_status()
    return parse_people(r.json())[0]


def _check(c, peer: dict, settings: Settings) -> dict:
    doc = kv.get("eu_peers", peer["domain"])
    if _fresh(doc) and "recent" in doc:
        return doc
    try:
        europe, _ = _count(c, peer["domain"], _EUROPE)
        total, _ = _count(c, peer["domain"], None)
    except Exception:
        return {**peer, "status": "unknown", "europe_people": 0}
    status = "yes" if europe >= 10 else "no" if europe < 3 and total >= settings.apollo_min_profiles else "unknown"
    try:
        recent = _recent_europe(c, peer["domain"]) if status == "yes" else 0
    except Exception:
        recent = 0
    doc = {**peer, "status": status, "europe_people": europe, "recent": recent, "total": total,
           "fetched_at": time.time()}
    kv.put("eu_peers", peer["domain"], doc)
    return doc


def cohort(domain: str, org: dict | None, sector_label: str | None, settings: Settings) -> dict | None:
    if not org or not settings.apollo_enabled:
        return None
    domain = normalise_domain(domain)
    body = filters(org)
    if body is None:
        return None
    cached = kv.get("eu_cohorts", domain)
    if _fresh(cached) and cached.get("filters") == body:
        found = cached["peers"]
    else:
        try:
            r = httpx.post(f"{_API}/mixed_companies/search", json=body, headers=_headers(settings), timeout=_TIMEOUT)
            r.raise_for_status()
            found = parse_peers(r.json(), domain, org.get("name"), None)[:_MAX]
        except Exception:
            return None
        kv.put("eu_cohorts", domain, {"peers": found, "filters": body, "fetched_at": time.time()})
    if not found:
        return None
    with httpx.Client(timeout=_TIMEOUT, headers=_headers(settings)) as c, ThreadPoolExecutor(max_workers=6) as pool:
        checked = list(pool.map(lambda p: _check(c, p, settings), found))
    known = [p for p in checked if p["status"] in ("yes", "no")]
    yes = [p for p in known if p["status"] == "yes"]
    rev = org.get("revenue_eur")
    band = ""
    if rev:
        lo, hi = rev / 3, rev * 3
        fmt = lambda v: f"{v / 1e9:.0f}bn" if v >= 1e9 else f"{max(10, round(v / 1e7) * 10):.0f}m"
        band = f", EUR {fmt(lo)} to {fmt(hi)} revenue"
    return {"peers": checked, "known": len(known), "with_presence": len(yes),
            "europe_people": sum(p["europe_people"] for p in yes),
            "recent_people": sum(p.get("recent", 0) for p in yes),
            "definition": f"Indian {(sector_label or 'industry').lower()} companies{band}",
            "publishable": len(known) >= _MIN_KNOWN}
