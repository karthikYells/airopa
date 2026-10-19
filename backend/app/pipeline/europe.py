"""Europe Market Assessment pipeline: one Indian company, end to end.

Website (products, certifications, languages, group sites) -> what they sell
(checked HS codes / service types) -> Europe's demand and tariffs per product
(Eurostat, WITS) -> Europe presence (Apollo free search + site) -> optional
company record (Apollo, 1 credit) and annual report -> two scores, country
ranking, time to first order. Independent lookups run in parallel.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app.adapters import apollo as apollo_adapter
from app.adapters import eurostat, wits
from app.adapters.web_scraper import scrape_with_deadline
from app.config import Settings
from app.data.records import ScoreResult
from app.reference import europe_reference as ref
from app.scoring import europe as scoring
from app.signals import europe_peers, europe_presence
from app.signals.products import Offering, map_offering

EU9 = ["DE", "IT", "FR", "NL", "ES", "BE", "PL", "SE", "CZ"]
COUNTRY_NAMES = {**europe_presence.COUNTRIES}


@dataclass
class EuropeAssessment:
    input_url: str
    domain: str
    name: str | None = None
    reachable: bool = False
    site_note: str | None = None
    org: dict | None = None
    offering: Offering | None = None
    demand: list = field(default_factory=list)       # [{product, view, tariff}]
    services: list = field(default_factory=list)     # reference service rows
    presence: europe_presence.EuropePresence | None = None
    certs: list = field(default_factory=list)
    site_text: str = ""
    financials: dict | None = None
    report_url: str | None = None
    report_cert_text: str = ""
    countries: list = field(default_factory=list)    # top 3
    uk_note: str | None = None
    peer_cohort: dict | None = None
    buyer_view: dict | None = None
    market: ScoreResult | None = None
    ready: ScoreResult | None = None
    time_range: dict | None = None
    timings: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)


def _country_rows_goods(hs: str) -> list[dict]:
    cells = eurostat.goods_imports([hs], EU9, [eurostat.EXTRA_EU, "IN"], ["2023", "2025"])
    get = {(c["reporter"], c["partner"], c["time"]): c["value"] for c in cells}
    rows = []
    for code in EU9:
        ext, ext0 = get.get((code, eurostat.EXTRA_EU, "2025")), get.get((code, eurostat.EXTRA_EU, "2023"))
        if ext:
            rows.append({"code": code, "name": COUNTRY_NAMES[code], "extra": ext,
                         "india": get.get((code, "IN", "2025")),
                         "growth": (ext / ext0) ** 0.5 - 1 if ext0 else None})
    return rows


def _country_rows_services(codes: list[str]) -> list[dict]:
    rows = []
    for code in EU9:
        cells = eurostat.services_imports(codes, ["EXT_EU27_2020", "IN"], ["2022", "2024"], geo=code)
        get = {}
        for c in cells:
            k = (c["partner"], c["time"])
            get[k] = get.get(k, 0) + (c["value"] or 0) * 1e6
        ext, ext0 = get.get(("EXT_EU27_2020", "2024")), get.get(("EXT_EU27_2020", "2022"))
        if ext:
            rows.append({"code": code, "name": COUNTRY_NAMES[code], "extra": ext,
                         "india": get.get(("IN", "2024")),
                         "growth": (ext / ext0) ** 0.5 - 1 if ext0 else None})
    return rows


def _annual_report(a: EuropeAssessment, scrape, llm) -> None:
    from app.signals.annual_report import fetch_report_pages, verify_financials
    if not (llm and llm.enabled and scrape.annual_report_urls):
        return
    certs: list[str] = []
    got = fetch_report_pages(scrape.annual_report_urls, cert_lines=certs)
    if not got:
        return
    url, pages = got
    a.report_cert_text = "\n".join(certs)
    fin = verify_financials(llm.extract_financials(a.name or "", pages), pages)
    # A report more than two years old is not their current position.
    if fin and fin["years"] and fin["years"][0]["year"] >= time.gmtime().tm_year - 2:
        ys = fin["years"]
        latest, prev = ys[0], (ys[1] if len(ys) > 1 else None)

        def margin(y):
            return y["op_profit"] / y["revenue"] if y and y["op_profit"] is not None and y["revenue"] else None
        a.financials = {"year": latest["year"], "revenue": latest["revenue"],
                        "revenue_growth": (latest["revenue"] / prev["revenue"] - 1) if prev and prev["revenue"] else None,
                        "op_margin": margin(latest), "op_margin_prev": margin(prev), "currency": fin["currency"]}
        a.report_url = url


def run(input_url: str, settings: Settings, llm=None) -> EuropeAssessment:
    t0 = time.monotonic()
    domain = apollo_adapter.normalise_domain(input_url.split("//")[-1])
    a = EuropeAssessment(input_url=input_url, domain=domain)
    sr = scrape_with_deadline(input_url, products=True)
    a.reachable, a.site_note = sr.reachable, sr.error
    a.timings["scrape"] = round(time.monotonic() - t0, 1)
    a.site_text = "\n".join([sr.homepage_text, sr.trust_text] + [p["text"] for p in sr.product_pages])
    a.certs = scoring.find_certs(a.site_text)

    with ThreadPoolExecutor(max_workers=4) as pool:
        f_org = pool.submit(apollo_adapter.enrich_org, domain, settings) if settings.apollo_europe_enrich else None
        f_pres = pool.submit(europe_presence.assess, domain, sr, settings)
        a.org = f_org.result() if f_org else None
        a.name = (a.org or {}).get("name") or sr.page_title_name or domain.split(".")[0].title()
        f_off = pool.submit(map_offering, a.name, sr, llm) if sr.reachable else None
        f_rep = pool.submit(_annual_report, a, sr, llm)
        f_peer = pool.submit(europe_peers.cohort, domain, a.org, None, settings) if a.org else None
        a.offering = f_off.result() if f_off else None
        a.timings["offering"] = round(time.monotonic() - t0, 1)

        # Demand and tariffs per product (top 3), in parallel.
        prods = a.offering.products[:3] if a.offering else []
        views = list(pool.map(lambda p: eurostat.demand_view(p["hs"]), prods))
        a.demand = [{"product": p, "view": v, "tariff": None} for p, v in zip(prods, views)]
        best = max((d for d in a.demand if d["view"]), key=lambda d: d["view"]["extra_eu"], default=None)
        f_tar = pool.submit(wits.mfn_tariff, best["product"]["hs"]) if best and len(best["product"]["hs"]) == 6 else None
        is_services = a.offering is not None and a.offering.kind == "services"
        f_buy = pool.submit(eurostat.industry_view, a.offering.buyers) if a.offering and a.offering.buyers else None
        if is_services:
            codes = sorted({s["code"] for s in a.offering.services})
            f_cty = pool.submit(_country_rows_services, codes)
        elif best:
            f_cty = pool.submit(_country_rows_goods, best["view"]["hs"])
        else:
            f_cty = None
        a.presence = f_pres.result()
        if f_tar:
            best["tariff"] = f_tar.result()
        rows = f_cty.result() if f_cty else []
        f_rep.result()
        a.peer_cohort = f_peer.result() if f_peer else None
        a.buyer_view = f_buy.result() if f_buy else None
    # Certifications named in their own annual report count as well.
    a.certs = scoring.find_certs(a.site_text + "\n" + a.report_cert_text)
    a.services = ref.services()
    a.countries = scoring.rank_countries(rows, a.presence, is_services)
    # Eurostat stopped covering the UK after Brexit, so the UK is named from
    # their own presence and the agreement in force, without an import figure.
    uk = a.presence.by_country.get("UK", 0) if a.presence else 0
    if uk >= 5 or is_services:
        a.uk_note = ("United Kingdom: the UK–India agreement has applied since 15 July 2026"
                     + (f", and you already have {uk} people there." if uk else "."))
    a.market = scoring.market_opportunity(a)
    a.ready = scoring.readiness(a)
    a.time_range = scoring.time_to_first_order(a, a.ready)
    a.timings["total"] = round(time.monotonic() - t0, 1)
    if not sr.reachable:
        a.notes.append(f"Website not read: {sr.error}")
    return a
