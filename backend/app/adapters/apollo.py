"""Apollo.io adapter — people and firmographic data for the India gate and scale.

The site crawl cannot see India headcount (careers often live on a separate
domain, and nav menus get mistaken for job titles). Apollo's people database
can: it returns how many of a company's people are based in India and what
their titles are — the GATE.04 / GATE.06 inputs the spec actually asks for.

Calls and credit cost (Apollo pricing, per company):
  - people api_search (India-located staff + titles)     free
  - organizations/enrich (revenue, headcount, founded)   1 credit
  - organizations/{id}/job_postings (India openings)     1 credit
Paid calls are separate switches: `apollo_enrich` (on) and `apollo_job_postings` (off).
Leadership appointed in the last 12 months comes from two more free searches. Every response is
cached per domain (app.data.kv) for `apollo_cache_days`, so re-scoring a company costs
nothing. Missing fields stay None (honest UNKNOWN upstream).
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

import httpx

from app.data import kv
from app.config import Settings

_API = "https://api.apollo.io/api/v1"
_TIMEOUT = httpx.Timeout(20.0, connect=6.0)
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
    city: str | None = None
    naics_codes: list[str] = field(default_factory=list)  # industry codes, for the peer search
    sic_codes: list[str] = field(default_factory=list)
    employees: int | None = None
    revenue_eur: int | None = None
    total_people_count: int = 0   # all profiles at the domain: Apollo's coverage
    india_people_count: int = 0
    india_titles: list[str] = field(default_factory=list)
    india_job_titles: list[str] = field(default_factory=list)
    job_postings_checked: bool = False
    leadership_checked: bool = False
    new_tech_leaders: list[str] = field(default_factory=list)      # titles, last 365 days
    new_business_leaders: list[str] = field(default_factory=list)  # titles, last 365 days
    credits_used: int = 0
    from_cache: bool = False
    fetched_at: float = 0.0

    @property
    def as_of(self) -> str:
        """Date Apollo was queried (may be earlier than today when cached)."""
        return time.strftime("%Y-%m-%d", time.localtime(self.fetched_at or time.time()))

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


def parse_org_name(data: dict) -> str | None:
    """The employer name most people in a search result share."""
    names = [((p.get("organization") or {}).get("name") or "").strip()
             for p in data.get("people") or []]
    names = [n for n in names if n]
    return max(set(names), key=names.count) if names else None


def parse_org(data: dict) -> dict:
    org = data.get("organization") or {}
    rev = org.get("annual_revenue")
    return {
        "org_id": org.get("id"),
        "name": org.get("name"),
        "country": org.get("country"),
        "industry": org.get("industry"),
        "founded_year": org.get("founded_year"),
        "city": org.get("city"),
        "naics_codes": [str(x) for x in org.get("naics_codes") or []],
        "sic_codes": [str(x) for x in org.get("sic_codes") or []],
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
def _load_cache(domain: str, max_age_days: int) -> ApolloResult | None:
    raw = kv.get("apollo", domain)
    if raw is None:
        return None
    try:
        if time.time() - raw.get("fetched_at", 0) > max_age_days * 86400:
            return None
        res = ApolloResult(**raw)
        res.from_cache, res.credits_used = True, 0
        return res
    except Exception:
        return None


def _save_cache(res: ApolloResult) -> None:
    kv.put("apollo", res.domain, asdict(res))


_TECH_EXEC_TITLES = ["chief information officer", "chief technology officer",
                     "chief digital officer", "CIO", "CTO", "CDO"]
_BUSINESS_EXEC_TITLES = ["chief executive officer", "chief financial officer",
                         "chief operating officer", "CEO", "CFO", "COO"]

def _recent_titles(c: httpx.Client, domain: str, titles: list[str]) -> list[str] | None:
    """Exact-title search for people in post at most 365 days. Returns their
    titles (deduplicated), [] for none, None if the search itself failed."""
    try:
        r = c.post(f"{_API}/mixed_people/api_search", json={
            "q_organization_domains_list": [domain], "person_titles": titles,
            "include_similar_titles": False,
            "person_days_in_current_title_range": {"max": 365},
            "per_page": 10, "page": 1})
        r.raise_for_status()
        _, found = parse_people(r.json())
        return list(dict.fromkeys(found))
    except Exception:
        return None


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
            # Free: all profiles at the domain. Distinguishes "no India staff"
            # (company well covered, none in India) from "Apollo does not know
            # this company" (no profiles at all).
            r = c.post(f"{_API}/mixed_people/api_search", params=[
                ("q_organization_domains_list[]", domain),
                ("per_page", 5), ("page", 1)])
            r.raise_for_status()
            res.total_people_count, _ = parse_people(r.json())
            res.name = parse_org_name(r.json())
        except Exception:
            return None

        # Free: leadership appointed in the last 12 months (PRESS.10 / PRESS.11).
        # Titles only; names never leave the engine.
        res.new_tech_leaders = _recent_titles(c, domain, _TECH_EXEC_TITLES)
        res.new_business_leaders = _recent_titles(c, domain, _BUSINESS_EXEC_TITLES)
        res.leadership_checked = res.new_tech_leaders is not None
        res.new_tech_leaders = res.new_tech_leaders or []
        res.new_business_leaders = res.new_business_leaders or []

        # Paid calls: each guarded separately so a later failure never discards
        # data a credit was already spent on.
        if settings.apollo_paid_calls or settings.apollo_enrich:
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
        if res.org_id and (settings.apollo_paid_calls or settings.apollo_job_postings):
            try:
                r = c.get(f"{_API}/organizations/{res.org_id}/job_postings",
                          params={"per_page": 1000})
                if r.status_code < 400:
                    res.credits_used += 1
                    res.job_postings_checked = True
                    res.india_job_titles = parse_india_postings(r.json())
            except Exception:
                pass

    # Found = Apollo knows the company well enough that its India count means
    # something. A handful of profiles is too thin to call "no India staff".
    res.found = bool(res.org_id or res.india_people_count
                     or res.total_people_count >= settings.apollo_min_profiles)
    _save_cache(res)
    return res


def enrich_org(domain: str, settings: Settings) -> dict | None:
    """Apollo's company record for one domain (1 credit), cached in the store
    for `apollo_cache_days`. Used by the Europe Market Assessment for revenue,
    headcount, industry codes and city. None if Apollo is off or knows nothing."""
    if not settings.apollo_enabled:
        return None
    domain = normalise_domain(domain)
    doc = kv.get("apollo_org", domain)
    if doc and time.time() - doc.get("fetched_at", 0) < settings.apollo_cache_days * 86400:
        return doc.get("org")
    headers = {"X-Api-Key": settings.apollo_api_key, "Cache-Control": "no-cache"}
    try:
        r = httpx.get(f"{_API}/organizations/enrich", params={"domain": domain},
                      headers=headers, timeout=_TIMEOUT)
        org = parse_org(r.json()) if r.status_code < 400 else None
    except Exception:
        return None
    org = org if org and org.get("org_id") else None
    kv.put("apollo_org", domain, {"org": org, "fetched_at": time.time()})
    return org
