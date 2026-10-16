"""Apollo.io adapter — people and firmographic data for the India gate and scale.

The site crawl cannot see India headcount (careers often live on a separate
domain, and nav menus get mistaken for job titles). Apollo's people database
can: it returns how many of a company's people are based in India and what
their titles are — the GATE.04 / GATE.06 inputs the spec actually asks for.

Calls and credit cost (Apollo pricing, per company):
  - people api_search (India-located staff + titles)     free
  - organizations/enrich (revenue, headcount, founded)   1 credit
  - organizations/{id}/job_postings (India openings)     1 credit
The two paid calls run only when `apollo_paid_calls` is on (off by default). Every response is
cached per domain on disk for `apollo_cache_days`, so re-scoring a company costs
nothing. Missing fields stay None (honest UNKNOWN upstream).
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

from app.config import Settings

_API = "https://api.apollo.io/api/v1"
_TIMEOUT = httpx.Timeout(20.0, connect=6.0)
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "apollo_cache"
_USD_TO_EUR = 0.92  # same rough rate the Wikidata adapter uses


@dataclass
class ApolloResult:
    found: bool = False
    domain: str = ""
    org_id: str | None = None
    name: str | None = None
    country: str | None = None
    industry: str | None = None
    founded_year: int | None = None
    employees: int | None = None
    revenue_eur: int | None = None
    india_people_count: int = 0
    india_titles: list[str] = field(default_factory=list)
    india_job_titles: list[str] = field(default_factory=list)
    job_postings_checked: bool = False
    credits_used: int = 0
    from_cache: bool = False
    fetched_at: float = 0.0

    @property
    def source_url(self) -> str:
        return f"https://app.apollo.io/#/companies?domain={self.domain}"


def normalise_domain(host: str) -> str:
    h = (host or "").lower().strip().split("/")[0].split(":")[0]
    return h[4:] if h.startswith("www.") else h


# --- response parsing (pure, unit-tested) -----------------------------------
def parse_people(data: dict) -> tuple[int, list[str]]:
    people = data.get("people") or []
    total = data.get("total_entries")
    if total is None:
        total = (data.get("pagination") or {}).get("total_entries", len(people))
    titles = [p["title"].strip() for p in people if (p.get("title") or "").strip()]
    return int(total or 0), titles


def parse_org(data: dict) -> dict:
    org = data.get("organization") or {}
    rev = org.get("annual_revenue")
    return {
        "org_id": org.get("id"),
        "name": org.get("name"),
        "country": org.get("country"),
        "industry": org.get("industry"),
        "founded_year": org.get("founded_year"),
        "employees": org.get("estimated_num_employees"),
        "revenue_eur": int(rev * _USD_TO_EUR) if isinstance(rev, (int, float)) and rev > 0 else None,
    }


def parse_india_postings(data: dict) -> list[str]:
    posts = data.get("organization_job_postings") or data.get("job_postings") or []
    out = []
    for p in posts:
        where = " ".join(str(p.get(k) or "") for k in ("country", "state", "city")).lower()
        if "india" in where and (p.get("title") or "").strip():
            out.append(p["title"].strip())
    return out


# --- cache --------------------------------------------------------------------
def _cache_path(domain: str) -> Path:
    return _CACHE_DIR / f"{domain.replace('/', '_')}.json"


def _load_cache(domain: str, max_age_days: int) -> ApolloResult | None:
    path = _cache_path(domain)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - raw.get("fetched_at", 0) > max_age_days * 86400:
            return None
        res = ApolloResult(**raw)
        res.from_cache, res.credits_used = True, 0
        return res
    except Exception:
        return None


def _save_cache(res: ApolloResult) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(res.domain).write_text(json.dumps(asdict(res)), encoding="utf-8")
    except Exception:
        pass


# --- live fetch -----------------------------------------------------------------
def fetch(host: str, settings: Settings) -> ApolloResult | None:
    """Apollo data for a domain, or None when Apollo is off or unreachable."""
    if not settings.apollo_enabled:
        return None
    domain = normalise_domain(host)
    cached = _load_cache(domain, settings.apollo_cache_days)
    if cached is not None:
        return cached

    res = ApolloResult(domain=domain, fetched_at=time.time())
    headers = {"X-Api-Key": settings.apollo_api_key, "Cache-Control": "no-cache",
               "Content-Type": "application/json"}
    with httpx.Client(timeout=_TIMEOUT, headers=headers) as c:
        # Free: India-located people at this domain. If this fails, Apollo is
        # unusable for the run and the engine falls back to the crawl.
        try:
            r = c.post(f"{_API}/mixed_people/api_search", params=[
                ("q_organization_domains_list[]", domain),
                ("person_locations[]", "India"),
                ("per_page", 100), ("page", 1)])
            r.raise_for_status()
            res.india_people_count, res.india_titles = parse_people(r.json())
        except Exception:
            return None

        # Paid calls: each guarded separately so a later failure never discards
        # data a credit was already spent on.
        if settings.apollo_paid_calls:
            try:
                r = c.get(f"{_API}/organizations/enrich", params={"domain": domain})
                if r.status_code < 400:
                    org = parse_org(r.json())
                    if org["org_id"]:
                        res.credits_used += 1
                        for k, v in org.items():
                            setattr(res, k, v)
            except Exception:
                pass
            if res.org_id:
                try:
                    r = c.get(f"{_API}/organizations/{res.org_id}/job_postings",
                              params={"per_page": 1000})
                    if r.status_code < 400:
                        res.credits_used += 1
                        res.job_postings_checked = True
                        res.india_job_titles = parse_india_postings(r.json())
                except Exception:
                    pass

    res.found = bool(res.org_id or res.india_people_count or res.india_titles)
    _save_cache(res)
    return res
