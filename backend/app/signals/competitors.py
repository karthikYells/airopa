"""Competitors with the same offering that are already in Europe.

Two sources of candidates: Claude names companies known to sell the same
offering (a market analyst's list), and one Apollo company search on the
offering's keywords (1 credit). Every candidate is then checked against its
own homepage: Claude must quote a phrase from that page showing the same kind
of offering, and the code keeps the candidate only if the phrase is really on
the page. A candidate whose site cannot be read is dropped, never assumed.

Europe presence and origin come from Apollo's free people search: 5 or more
Europe-based people counts as present; a company with most of its people in
India counts as an Indian rival. Names never go to the public page: they are
kept with the run on the server and used only in the emailed PDF (top three).
Results are kept in the shared store for 90 days per prospect.
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.adapters.apollo import _API, _TIMEOUT, normalise_domain
from app.config import Settings
from app.data import kv
from app.signals.europe_presence import _count
from app.signals.peers import parse_peers

_TTL = 90 * 86400
_EUROPE = ["European Union", "United Kingdom", "Switzerland", "Norway"]
_MIN_EUROPE = 5
_DOMAIN = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _homepage(domain: str) -> str:
    from app.adapters.web_scraper import _text
    try:
        r = httpx.get(f"https://{domain}", timeout=httpx.Timeout(8.0, connect=4.0), follow_redirects=True,
                      headers={"User-Agent": "AiropaBot/1.0 (+https://airopa.co)"})
        return _text(r.text)[:6000] if r.status_code < 400 else ""
    except Exception:
        return ""


def _search(keywords: list[str], own: str, settings: Settings) -> list[dict]:
    if not keywords or not settings.apollo_enabled:
        return []
    body = {"q_organization_keyword_tags": keywords[:3], "per_page": 25, "page": 1}
    try:
        r = httpx.post(f"{_API}/mixed_companies/search", json=body, timeout=_TIMEOUT,
                       headers={"X-Api-Key": settings.apollo_api_key, "Cache-Control": "no-cache",
                                "Content-Type": "application/json"})
        r.raise_for_status()
        return parse_peers(r.json(), own, None, None)
    except Exception:
        return []


def find(domain: str, name: str | None, offering, settings: Settings, llm) -> dict | None:
    """{competitors: [...], in_europe, indian_in_europe, europe_people, recent_people} or None."""
    if not offering or not offering.segment or llm is None or not getattr(llm, "enabled", False):
        return None
    own = normalise_domain(domain)
    cached = kv.get("competitors", own)
    if cached and time.time() - cached.get("fetched_at", 0) < _TTL:
        return cached
    lines = [p["name"] for p in offering.products] + [s["name"] for s in offering.services]
    prop = llm.propose_competitors(name or own, offering.segment, lines)
    cands: dict[str, dict] = {}
    for c in prop.get("competitors") or []:
        d = normalise_domain(str(c.get("domain") or ""))
        if _DOMAIN.match(d) and d != own and d not in cands:
            cands[d] = {"name": str(c.get("name") or d)[:80], "domain": d, "source": "analyst"}
    for c in _search([str(k) for k in (prop.get("keywords") or []) if k], own, settings):
        if c["domain"] not in cands and len(cands) < 30:
            cands[c["domain"]] = {"name": c["name"], "domain": c["domain"], "source": "search"}
    if not cands:
        return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        texts = list(pool.map(lambda c: _homepage(c["domain"]), cands.values()))
    readable = [{**c, "text": t} for c, t in zip(cands.values(), texts) if len(t) > 200]
    verdicts = {}
    for i in range(0, len(readable), 12):
        verdicts.update(llm.check_competitors(offering.segment, readable[i:i + 12]))
    confirmed = []
    for c in readable:
        ev = verdicts.get(c["domain"])
        if isinstance(ev, str) and len(_norm(ev)) >= 8 and _norm(ev) in _norm(c["text"]):
            confirmed.append({k: c[k] for k in ("name", "domain", "source")} | {"evidence": ev[:160]})

    headers = {"X-Api-Key": settings.apollo_api_key, "Cache-Control": "no-cache", "Content-Type": "application/json"}

    def presence(c: dict) -> dict:
        try:
            with httpx.Client(timeout=_TIMEOUT, headers=headers) as cl:
                eu, _ = _count(cl, c["domain"], _EUROPE)
                india, _ = _count(cl, c["domain"], ["India"])
                total, _ = _count(cl, c["domain"], None)
                recent = 0
                if eu >= _MIN_EUROPE:
                    from app.signals.europe_peers import _recent_europe
                    recent = _recent_europe(cl, c["domain"])
        except Exception:
            return {**c, "europe_people": 0, "known": False}
        return {**c, "europe_people": eu, "india_people": india, "total": total, "recent": recent,
                "indian": total > 0 and india / total >= 0.5, "known": total >= 20}

    with ThreadPoolExecutor(max_workers=6) as pool:
        checked = list(pool.map(presence, confirmed)) if settings.apollo_enabled else []
    in_eu = sorted([c for c in checked if c.get("europe_people", 0) >= _MIN_EUROPE],
                   key=lambda c: -c["europe_people"])
    out = {"competitors": checked, "in_europe": len(in_eu),
           "indian_in_europe": sum(1 for c in in_eu if c.get("indian")),
           "europe_people": sum(c["europe_people"] for c in in_eu),
           "recent_people": sum(c.get("recent", 0) for c in in_eu),
           "named": [{"name": c["name"], "domain": c["domain"], "europe_people": c["europe_people"],
                      "indian": c.get("indian", False)} for c in in_eu[:3]],
           "candidates": len(cands), "confirmed": len(confirmed), "fetched_at": time.time()}
    kv.put("competitors", own, out)
    return out
