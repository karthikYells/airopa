"""Signal collection — turns a seed entity, or a live crawl + Wikidata + the
India reference dataset, into evidence.

The live path is what makes the engine work for ANY domain: firmographics come
from Wikidata and the company's own site (honest UNKNOWN where absent), India
presence from a systematic site crawl plus Wikidata subsidiaries, and the India
Market and Technology Hub inputs from the sector-keyed reference dataset
(Section 6.2) so those two public scores resolve for every classified company.
"""
from __future__ import annotations

from datetime import date

from app.adapters.apollo import ApolloResult
from app.adapters.web_scraper import ScrapeResult
from app.adapters.wikidata import WikidataEntity
from app.config import Settings
from app.data.evidence import (
    Evidence, Method, SourceAuthority, SourceType, UNKNOWN,
)
from app.data.records import ClassifiedTitle, CompanyRecord, TitleClass
from app.fixtures.demo_companies import Seed
from app.gate.india_gate import GateInputs
from app.gate.title_classifier import classify_titles
from app.reference.india_reference import SectorReference, AS_OF, SOURCE
from app.signals.sector import classify_sector

# Wikidata country label -> Airopa geography code (X14).
_COUNTRY_CODE = {
    "Germany": "DE", "Netherlands": "NL", "Belgium": "BE",
    "United Kingdom": "UK", "France": "FR",
    "Sweden": "Nordics", "Norway": "Nordics", "Denmark": "Nordics",
    "Finland": "Nordics", "Iceland": "Nordics",
}


def _gate_inputs_from_titles(*, entity_exists, india_headcount, classified,
                             postings, announcement, parent_gcc, nic_codes,
                             records, min_records_override=None) -> GateInputs:
    tech = sum(1 for c in classified if c.title_class is TitleClass.TECH)
    it_support = sum(1 for c in classified if c.title_class is TitleClass.IT_SUPPORT)
    share = (tech / india_headcount) if isinstance(india_headcount, int) and india_headcount else 0.0
    return GateInputs(
        india_entity_exists=entity_exists, india_entity_nic_codes=nic_codes,
        india_headcount_total=india_headcount, india_tech_role_count=tech,
        india_tech_role_share=share, india_tech_job_postings_12m=postings,
        public_gcc_announcement=announcement, parent_has_india_gcc=parent_gcc,
        gate_evidence_records=records, classified_titles=classified,
        it_support_count=it_support, min_records_override=min_records_override,
    )


# ---------------------------------------------------------------------------
# Seed path (illustrative example companies) — unchanged behaviour.
# ---------------------------------------------------------------------------
def collect_from_seed(rec: CompanyRecord, seed: Seed, llm=None) -> GateInputs:
    rec.resolved_name = seed.legal_name
    rec.registry_id = seed.registry_id
    rec.jurisdiction = seed.jurisdiction
    rec.country = seed.country
    rec.sector = seed.sector
    rec.ultimate_parent = seed.ultimate_parent
    rec.subsidiaries = seed.subsidiaries
    rec.from_seed = True

    src = "https://reference.airopa.internal/illustrative"
    rec.add(Evidence("IDENT.08", seed.founding_year, source_url=src,
                     source_type=SourceType.REGISTRY, source_authority=SourceAuthority.PRIMARY,
                     confidence=0.9, method=Method.LOOKUP, as_of_date="2026-01-15"))
    rec.add(Evidence("SCALE.01", seed.revenue, unit="EUR", source_url=src,
                     source_type=SourceType.FILING, source_authority=SourceAuthority.PRIMARY,
                     confidence=0.85, method=Method.LOOKUP, as_of_date="2025-12-31"))
    rec.add(Evidence("SCALE.04", seed.headcount, unit="people", source_url=src,
                     source_type=SourceType.FILING, source_authority=SourceAuthority.PRIMARY,
                     confidence=0.85, method=Method.LOOKUP, as_of_date="2025-12-31"))
    if seed.state_majority:
        rec.add(Evidence("OWN.state_majority", True, source_url=src,
                         source_type=SourceType.REGISTRY, confidence=0.9,
                         method=Method.LOOKUP, as_of_date="2026-01-15"))
    for ev in seed.signals:
        rec.add(ev)

    classified = classify_titles(
        seed.tech_titles + seed.nontech_titles + ["IT Support"] * seed.it_support,
        llm=llm)
    rec.add(Evidence("GATE.09", seed.announcement, source_url=src,
                     source_type=SourceType.PRESS, confidence=0.8,
                     method=Method.LOOKUP, as_of_date="2026-01-15"))
    rec.add(Evidence("GATE.10", seed.parent_gcc, source_url=src,
                     source_type=SourceType.REGISTRY, confidence=0.8,
                     method=Method.LOOKUP, as_of_date="2026-01-15"))
    return _gate_inputs_from_titles(
        entity_exists=seed.entity_exists, india_headcount=seed.india_headcount,
        classified=classified, postings=seed.postings,
        announcement=seed.announcement, parent_gcc=seed.parent_gcc,
        nic_codes=seed.nic_codes, records=seed.records)


# ---------------------------------------------------------------------------
# Live path — the real "works for all" collector.
# ---------------------------------------------------------------------------
def _ref(signal_id, value, unit=None, conf=0.75, auth=SourceAuthority.SECONDARY,
         notes=None) -> Evidence:
    return Evidence(signal_id, value, unit=unit, as_of_date=AS_OF, source_url=SOURCE,
                    source_type=SourceType.REFERENCE_DATA, source_authority=auth,
                    confidence=conf, method=Method.LOOKUP, notes=notes)


def _apply_reference(rec: CompanyRecord, ref: SectorReference) -> None:
    """India reference signals (Section 6.2). Looked up, consistent per sector."""
    # India Market (DEM / POL)
    rec.add(_ref("DEM.02", ref.market_size_eur, unit="EUR"))
    rec.add(_ref("DEM.03", ref.market_growth, unit="growth"))
    rec.add(_ref("DEM.04", {"gdp_growth": 0.066, "industrial_production": 0.05}, unit="series"))
    rec.add(_ref("DEM.05", ref.segment_present))
    rec.add(_ref("DEM.06", ref.price_point_fit))
    rec.add(_ref("DEM.07", ref.adaptation))
    rec.add(_ref("DEM.08", ref.tariff_position))
    rec.add(_ref("DEM.09", ref.local_mfg_preference))
    rec.add(_ref("DEM.11", ref.peers_india_revenue))
    rec.add(_ref("DEM.13", ref.downstream_growth, unit="growth"))
    rec.add(_ref("DEM.14", ref.foreign_entrants_succeed))
    rec.add(_ref("DEM.15", {"route": ref.route_to_market}))
    rec.add(_ref("DEM.16", {"approval_lead_months": ref.approval_lead_months}))
    rec.add(_ref("POL.01", ref.pli_scheme))
    rec.add(_ref("POL.02", ref.fdi_route))
    rec.add(_ref("POL.06", {"trade_agreement": ref.trade_agreement}))
    rec.add(_ref("POL.07", ref.china_plus_one))
    rec.add(_ref("POL.08", ref.named_relocations))
    rec.add(_ref("POL.09", ref.pli_scheme))
    # Technology Hub (TAL / COST / SOV / PEER / IPR)
    rec.add(_ref("TAL.02", ref.talent_depth))
    rec.add(_ref("TAL.03", ref.talent_growth, unit="supply growth"))
    rec.add(_ref("TAL.04", ref.graduate_output, unit="graduates/yr"))
    rec.add(_ref("TAL.05", ref.sector_delivery_precedent))
    rec.add(_ref("TAL.06", ref.time_to_fill_india_wks, unit="weeks"))
    rec.add(_ref("TAL.07", ref.time_to_fill_home_wks, unit="weeks"))
    rec.add(_ref("TAL.08", ref.attrition, unit="attrition"))
    rec.add(_ref("TAL.09", ref.salary_india_eur, unit="EUR"))
    rec.add(_ref("TAL.10", ref.salary_home_eur, unit="EUR"))
    saving = round((ref.salary_home_eur - ref.salary_india_eur) / ref.salary_home_eur, 2)
    rec.add(_ref("TAL.11", f"{int(saving*100)-5} to {int(saving*100)}%", notes="fully loaded differential"))
    rec.add(_ref("TAL.12", ref.top_cities))
    rec.add(_ref("TAL.13", "office supply and direct flight links adequate"))
    rec.add(_ref("TAL.14", "high English proficiency, workable time zone overlap"))
    rec.add(_ref("TAL.15", ref.sector_delivery_precedent))
    rec.add(_ref("TAL.16", ref.gcc_density, unit="GCC/SI density"))
    rec.add(_ref("COST.05", f"{int(saving*100)-5} to {int(saving*100)}%", notes="indicative saving range"))
    rec.add(_ref("SOV.01", False, notes="no data residency commitment identified"))
    rec.add(_ref("SOV.02", {"restriction": "none material" if ref.sector != "Aerospace and defence" else "export controls"}))
    rec.add(_ref("SOV.03", 0.4 if "defence" in ref.sector.lower() else 0.03, unit="share"))
    rec.add(_ref("SOV.08", True, notes="GDPR transfer mechanism (SCCs) routinely available"))
    rec.add(_ref("PEER.30", ref.gcc_penetration, unit="penetration"))
    rec.add(_ref("PEER.32", ref.penetration_recent_24m, unit="recent 24m"))
    rec.add(_ref("PEER.13", ["engineering", "IT", "shared services"]))
    rec.add(_ref("IPR.30", ref.ip_intensity, notes="sector IP intensity"))


def _today() -> str:
    """As-of date for facts read live on this run (crawl, site evidence)."""
    return date.today().isoformat()


def _apply_apollo_firmographics(rec: CompanyRecord, ap: ApolloResult) -> None:
    """Fill scale signals Wikidata left UNKNOWN. Wikidata stays first choice."""
    def missing(sid: str) -> bool:
        ev = rec.get(sid)
        return ev is None or not ev.is_resolved

    common = dict(source_url=ap.source_url, source_type=SourceType.REFERENCE_DATA,
                  source_authority=SourceAuthority.SECONDARY, method=Method.API,
                  as_of_date=ap.as_of, notes="Apollo.io estimate")
    if ap.founded_year and missing("IDENT.08"):
        rec.add(Evidence("IDENT.08", ap.founded_year, confidence=0.6, **common))
    if ap.revenue_eur and missing("SCALE.01"):
        rec.add(Evidence("SCALE.01", ap.revenue_eur, unit="EUR", confidence=0.5, **common))
    if ap.employees and missing("SCALE.04"):
        rec.add(Evidence("SCALE.04", ap.employees, unit="people", confidence=0.55, **common))

    # Leadership appointed within the 12 months before the check (PRESS.10/11).
    # Titles only: names stay out of the record, and the public page names nobody.
    if ap.leadership_checked:
        people = dict(source_url=ap.source_url, source_type=SourceType.PEOPLE_DATA,
                      source_authority=SourceAuthority.SECONDARY, method=Method.API,
                      as_of_date=ap.as_of, confidence=0.6)
        rec.add(Evidence("PRESS.10", bool(ap.new_tech_leaders),
                         notes=("appointed within 12 months: " + ", ".join(ap.new_tech_leaders)
                                if ap.new_tech_leaders else "no CIO/CTO/CDO appointed within 12 months"),
                         **people))
        rec.add(Evidence("PRESS.11", bool(ap.new_business_leaders),
                         notes=("appointed within 12 months: " + ", ".join(ap.new_business_leaders)
                                if ap.new_business_leaders else "no CEO/CFO/COO appointed within 12 months"),
                         **people))


def collect_live(rec: CompanyRecord, scrape: ScrapeResult, wd: WikidataEntity,
                 ref: SectorReference, settings: Settings, llm=None,
                 apollo: ApolloResult | None = None) -> GateInputs:
    home = scrape.pages_fetched[0] if scrape.pages_fetched else scrape.input_url

    # --- firmographics from Wikidata (real, where present) ---
    if wd.found:
        if wd.inception_year:
            rec.add(Evidence("IDENT.08", wd.inception_year, source_url="https://www.wikidata.org/wiki/" + (wd.qid or ""),
                             source_type=SourceType.REGISTRY, source_authority=SourceAuthority.SECONDARY,
                             confidence=0.7, method=Method.API, as_of_date=AS_OF))
        if wd.revenue_eur:
            rec.add(Evidence("SCALE.01", wd.revenue_eur, unit="EUR",
                             source_url="https://www.wikidata.org/wiki/" + (wd.qid or ""),
                             source_type=SourceType.FILING, source_authority=SourceAuthority.SECONDARY,
                             confidence=0.6, method=Method.API,
                             as_of_date=(wd.revenue_year + "-12-31") if wd.revenue_year else AS_OF))
        if wd.employees:
            rec.add(Evidence("SCALE.04", wd.employees, unit="people",
                             source_url="https://www.wikidata.org/wiki/" + (wd.qid or ""),
                             source_type=SourceType.FILING, source_authority=SourceAuthority.SECONDARY,
                             confidence=0.6, method=Method.API, as_of_date=AS_OF))
        if wd.parent:
            rec.ultimate_parent = wd.parent
        if wd.subsidiaries:
            rec.subsidiaries = [{"name": s} for s in wd.subsidiaries]

    if apollo is not None and apollo.found:
        _apply_apollo_firmographics(rec, apollo)

    # --- scope from the live tech stack ---
    if scrape.tech_stack:
        erp = next((t for t in scrape.tech_stack if t.startswith("SAP")), None)
        if erp:
            rec.add(Evidence("SCOPE.01", erp, source_url=home, source_type=SourceType.JOB_POSTING,
                             source_authority=SourceAuthority.SECONDARY, confidence=0.55,
                             method=Method.PARSER, as_of_date=_today()))
        others = [t for t in scrape.tech_stack if not t.startswith("SAP")]
        if others:
            rec.add(Evidence("SCOPE.02", others, source_url=home, source_type=SourceType.JOB_POSTING,
                             confidence=0.5, method=Method.PARSER, as_of_date=_today()))
        legacy = [t for t in scrape.tech_stack if t == "Mainframe/COBOL"]
        if legacy:
            rec.add(Evidence("SCOPE.05", legacy, source_url=home, source_type=SourceType.JOB_POSTING,
                             confidence=0.5, method=Method.PARSER, as_of_date=_today()))

    # --- hiring from their own careers pages ---
    if scrape.job_titles:
        rec.add(Evidence("HIRE.01", len(scrape.job_titles), unit="open roles",
                         source_url=home, source_type=SourceType.COMPANY_SITE,
                         source_authority=SourceAuthority.PRIMARY, confidence=0.7,
                         method=Method.PARSER, as_of_date=_today()))
        classified_all = classify_titles(scrape.job_titles, llm=llm)
        tech_share = sum(1 for c in classified_all if c.title_class is TitleClass.TECH) / max(len(classified_all), 1)
        rec.add(Evidence("HIRE.04", round(tech_share, 2), unit="tech share",
                         source_url=home, source_type=SourceType.COMPANY_SITE,
                         confidence=0.5, method=Method.DICTIONARY, as_of_date=_today()))
    if scrape.tech_exec_named:
        rec.add(Evidence("ROUTE.01", True, source_url=home, source_type=SourceType.COMPANY_SITE,
                         confidence=0.6, method=Method.PARSER, as_of_date=_today()))

    # --- TAL.01: required skill families, derived from their estate (if any) ---
    if scrape.tech_stack:
        rec.add(Evidence("TAL.01", scrape.tech_stack[:5], source_type=SourceType.INFERENCE,
                         inference_inputs=["SCOPE.01", "SCOPE.02"], confidence=0.5,
                         method=Method.MODEL, as_of_date=_today(),
                         notes="Derived from the technology stack on their own site."))

    # --- India reference dataset (makes Scores B & C resolve) ---
    _apply_reference(rec, ref)
    rec.add(_ref("DEM.01", {"category": ref.sector}, conf=0.6))

    # --- India gate inputs ---
    if apollo is not None and apollo.found:
        return _india_gate_from_apollo(rec, scrape, wd, apollo, settings, llm, home)

    india_entity = wd.india_subsidiary or scrape.india_office_detected
    india_checks = scrape.india_checks + (2 if wd.found else 0) + len(scrape.india_pages)
    classified_india = classify_titles(scrape.india_careers_titles, llm=llm)
    if india_entity:
        rec.add(Evidence("GATE.01", True, source_url=(scrape.india_pages[0] if scrape.india_pages else home),
                         source_type=SourceType.INFERENCE,
                         inference_inputs=["site India office detection", "Wikidata subsidiaries"],
                         confidence=0.5, method=Method.MODEL, as_of_date=_today()))
        entity_val = True
    elif scrape.reachable and india_checks >= 3:
        rec.add(Evidence("GATE.01", False, source_url=home, source_type=SourceType.INFERENCE,
                         inference_inputs=[f"{india_checks} India-targeted checks, none positive"],
                         confidence=0.45, method=Method.MODEL, as_of_date=_today()))
        entity_val = False
    else:
        entity_val = UNKNOWN

    # Live crawls examine fewer but targeted India sources than a people search,
    # so the gate's thin-data floor is lower on this path (documented override).
    return _gate_inputs_from_titles(
        entity_exists=entity_val, india_headcount=UNKNOWN,
        classified=classified_india,
        postings=min(1, sum(1 for c in classified_india if c.title_class is TitleClass.TECH)),
        announcement=False, parent_gcc=False, nic_codes=[],
        records=india_checks, min_records_override=settings.gate_min_evidence_records_live)


def _india_gate_from_apollo(rec: CompanyRecord, scrape: ScrapeResult, wd: WikidataEntity,
                            ap: ApolloResult, settings: Settings, llm, home: str) -> GateInputs:
    """India gate from Apollo's people database (GATE.01/04/06/08).

    Apollo titles replace the crawl's careers-page titles, which on many sites
    are navigation text rather than jobs. India headcount is Apollo's count of
    India-located profiles; tech postings are India openings classed TECH.
    """
    people_src = dict(source_url=ap.source_url, source_type=SourceType.PEOPLE_DATA,
                      source_authority=SourceAuthority.SECONDARY, method=Method.API,
                      as_of_date=ap.as_of)
    india_entity = (ap.india_people_count >= settings.apollo_india_entity_min
                    or wd.india_subsidiary or scrape.india_office_detected)
    rec.add(Evidence("GATE.01", bool(india_entity), confidence=0.7 if india_entity else 0.6,
                     notes=(f"Apollo: {ap.india_people_count} India-located profiles "
                            f"(entity threshold {settings.apollo_india_entity_min}); "
                            f"Wikidata India subsidiary: {wd.india_subsidiary}; "
                            f"site India office: {scrape.india_office_detected}"),
                     **people_src))
    rec.add(Evidence("GATE.04", ap.india_people_count, unit="people", confidence=0.6,
                     notes="Apollo India-located profile count", **people_src))

    classified = classify_titles(ap.india_titles, llm=llm)
    postings_classified = classify_titles(ap.india_job_titles, llm=llm)
    tech_postings = sum(1 for c in postings_classified if c.title_class is TitleClass.TECH)
    if ap.job_postings_checked:
        rec.add(Evidence("GATE.08", tech_postings, unit="India tech postings", confidence=0.6,
                         notes=f"{len(ap.india_job_titles)} India postings on Apollo", **people_src))

    # Apollo is a people search across the whole company, so its evidence counts
    # for more than a single crawled page: one record per India profile sampled.
    records = scrape.india_checks + (2 if wd.found else 0) + max(len(ap.india_titles), 3)
    return _gate_inputs_from_titles(
        entity_exists=bool(india_entity), india_headcount=ap.india_people_count,
        classified=classified, postings=tech_postings,
        announcement=False, parent_gcc=False, nic_codes=[],
        records=records, min_records_override=settings.gate_min_evidence_records_live)


def country_code(wikidata_country: str | None) -> str | None:
    if not wikidata_country:
        return None
    return _COUNTRY_CODE.get(wikidata_country)
