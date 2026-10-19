"""Europe presence check for an Indian company (PRES cluster, spec section 4).

The mirror of the India gate. Verdicts:
  ESTABLISHED  a European entity (subsidiary, group site, office) and at least
               10 Europe-based people on public profiles
  EXPORTING    selling into Europe without a base: European staff or clear
               European customer/office signals, but no entity
  GREENFIELD   no Europe entity, staff or signals found
  UNKNOWN      Apollo barely knows the company and the site says nothing

Sources: Apollo's free people search (one call per target country, so we know
where in Europe they are), the titles of their Europe-based people (sales or
delivery), European subsidiary or group domains linked from their homepage,
European legal-entity names and countries on their own pages. Names of people
never leave the engine; only counts and title categories are kept.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx

from app.adapters.apollo import _API, _TIMEOUT, normalise_domain, parse_people
from app.config import Settings

# Apollo location names for the ranked target markets.
COUNTRIES = {"DE": "Germany", "IT": "Italy", "FR": "France", "NL": "Netherlands", "ES": "Spain",
             "BE": "Belgium", "PL": "Poland", "SE": "Sweden", "CZ": "Czechia", "UK": "United Kingdom",
             "IE": "Ireland", "AT": "Austria"}
_EU_TLDS = (".de", ".nl", ".fr", ".it", ".es", ".be", ".pl", ".se", ".cz", ".eu", ".co.uk", ".uk",
            ".at", ".ie", ".dk", ".fi", ".pt", ".ch")
_ENTITY = re.compile(r"\b(GmbH|B\.\s?V\.|S\.\s?r\.\s?l\.|S\.\s?p\.\s?A\.|S\.\s?A\.\s?S\.|SARL|S\.\s?L\.|"
                     r"Sp\.\s?z\s?o\.\s?o\.|s\.\s?r\.\s?o\.|AB|ApS|Oy|N\.\s?V\.|Ltd\.?\s*\(UK\)|UK Ltd|"
                     r"Europe (?:GmbH|B\.V\.|Ltd|S\.A\.|SAS|AB))\b")
_COUNTRY_WORDS = {code: name for code, name in COUNTRIES.items()}
_COUNTRY_WORDS.update({"UK": "United Kingdom|Britain|England", "NL": "Netherlands|Holland",
                       "CZ": "Czech Republic|Czechia"})
_COMMERCIAL = re.compile(r"sales|business development|account|country manager|country head|"
                         r"distribution|channel|marketing|customer|commercial|bd\b", re.I)
_DELIVERY = re.compile(r"engineer|developer|consultant|architect|project|technical|quality|"
                       r"plant|production|operations|delivery|analyst|scientist", re.I)


@dataclass
class EuropePresence:
    verdict: str = "UNKNOWN"
    reason: str = ""
    europe_people: int = 0                   # Europe + UK profiles at their domain(s)
    by_country: dict = field(default_factory=dict)    # code -> profiles
    commercial: int = 0                      # Europe titles that are sales/BD
    delivery: int = 0                        # Europe titles that are engineering/delivery
    total_people: int = 0                    # all profiles at the main domain
    eu_domains: list = field(default_factory=list)    # European sites linked from home
    entity_mentions: list = field(default_factory=list)  # e.g. "Sundram Fasteners GmbH"
    countries_on_site: list = field(default_factory=list)  # target countries named on their pages
    languages: list = field(default_factory=list)


def _count(c: httpx.Client, domain: str, locations: list[str] | None, per_page: int = 1):
    params = [("q_organization_domains_list[]", domain), ("per_page", per_page), ("page", 1)]
    params += [("person_locations[]", loc) for loc in (locations or [])]
    r = c.post(f"{_API}/mixed_people/api_search", params=params)
    r.raise_for_status()
    return parse_people(r.json())


def apollo_europe(domain: str, settings: Settings, extra_domains: list[str] = ()) -> dict | None:
    """Free people searches: Europe total and titles, per-country counts, total
    profiles. Subsidiary domains add to the Europe count. None if Apollo is off
    or fails."""
    if not settings.apollo_enabled:
        return None
    headers = {"X-Api-Key": settings.apollo_api_key, "Cache-Control": "no-cache",
               "Content-Type": "application/json"}
    europe = ["European Union", "United Kingdom", "Switzerland", "Norway"]
    try:
        with httpx.Client(timeout=_TIMEOUT, headers=headers) as c:
            total, _ = _count(c, domain, None)
            eu_total, titles = _count(c, domain, europe, per_page=100)
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=6) as pool:
                counts = list(pool.map(lambda nm: _count(c, domain, [nm])[0], COUNTRIES.values()))
            by_country = {code: n for code, n in zip(COUNTRIES, counts) if n}
            for d in list(extra_domains)[:3]:
                n, t = _count(c, d, europe, per_page=100)
                eu_total += n
                titles += t
    except Exception:
        return None
    return {"total": total, "europe": eu_total, "titles": titles, "by_country": by_country}


def site_signals(scrape) -> dict:
    """European entities, sites, countries and languages on their own pages."""
    pages = [scrape.homepage_text] + [p["text"] for p in getattr(scrape, "product_pages", [])]
    text = "\n".join(pages)
    entities = []
    for m in _ENTITY.finditer(text):
        start = max(0, m.start() - 40)
        snippet = re.sub(r"\s+", " ", text[start:m.end()]).strip()
        name = snippet.split("\n")[-1][-70:]
        if name not in entities:
            entities.append(name)
    countries = [code for code, words in _COUNTRY_WORDS.items()
                 if re.search(rf"\b({words})\b", text, re.I)]
    eu_domains = [d for d in getattr(scrape, "external_domains", []) if d.endswith(_EU_TLDS)]
    return {"entities": entities[:6], "countries": countries, "eu_domains": eu_domains[:6],
            "languages": [l for l in getattr(scrape, "languages", []) if l != "en"]}


def _own_group_domains(domain: str, eu_domains: list[str]) -> list[str]:
    """European domains that share the company's name (sundram.de for
    sundram.com): likely their own subsidiaries, not distributors."""
    stem = normalise_domain(domain).split(".")[0]
    stem = re.sub(r"(group|india|ltd|limited|industries)$", "", stem) or stem
    return [d for d in eu_domains if stem and stem[:5] in d.split(".")[0]]


def assess(domain: str, scrape, settings: Settings) -> EuropePresence:
    sig = site_signals(scrape)
    own_eu = _own_group_domains(domain, sig["eu_domains"])
    ap = apollo_europe(normalise_domain(domain), settings, extra_domains=own_eu)
    p = EuropePresence(eu_domains=own_eu or sig["eu_domains"][:3], entity_mentions=sig["entities"],
                       countries_on_site=sig["countries"], languages=sig["languages"])
    if ap:
        p.total_people, p.europe_people, p.by_country = ap["total"], ap["europe"], ap["by_country"]
        p.commercial = sum(1 for t in ap["titles"] if _COMMERCIAL.search(t))
        p.delivery = sum(1 for t in ap["titles"] if _DELIVERY.search(t) and not _COMMERCIAL.search(t))
    entity = bool(own_eu or sig["entities"])
    # Fifty or more people based in Europe cannot be employed without a
    # European base, whether or not the homepage names the entity.
    if p.europe_people >= 50:
        top = max(p.by_country, key=p.by_country.get) if p.by_country else None
        p.verdict = "ESTABLISHED"
        p.reason = (f"{p.europe_people} Europe-based people on public profiles"
                    + (f", most in {COUNTRIES[top]}" if top else "") + ".")
    elif entity and p.europe_people >= 10:
        p.verdict = "ESTABLISHED"
        p.reason = (f"European entity found ({(own_eu or sig['entities'])[0]}) and "
                    f"{p.europe_people} Europe-based people on public profiles.")
    elif p.europe_people >= 10 or (entity and p.europe_people >= 3):
        p.verdict = "EXPORTING" if not entity else "ESTABLISHED"
        p.reason = (f"{p.europe_people} Europe-based people on public profiles"
                    + (", and a European entity on your site." if entity else ", but no European entity found."))
    elif p.europe_people >= 3 or entity or len(sig["countries"]) >= 3:
        p.verdict = "EXPORTING"
        p.reason = "Some European activity (staff, entity or markets named on your site), but no established base."
    elif ap and p.total_people >= settings.apollo_min_profiles:
        p.verdict = "GREENFIELD"
        p.reason = "No European entity, staff or markets found."
    else:
        p.verdict = "UNKNOWN"
        p.reason = "Too little public data to judge your European presence."
    return p
