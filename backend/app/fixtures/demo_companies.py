"""Seeded verified-entity store (stands in for Section 6.1 / 6.2 data).

Until Airopa licenses the registry, people-search and India reference datasets,
this seed provides a handful of FICTIONAL, illustrative companies so the engine
can demonstrate every response mode (Section 9.4) with full three-score output.
Every company and figure here is fictional and illustrative — exactly the
convention the spec uses for its own mockups (Section 9.9).

Each entry carries real evidence envelopes: reference-data signals use
source_type=reference_data / method=lookup, as the spec requires (Section 6.2),
so coverage and traceability behave as they will in production.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.data.evidence import (
    Evidence, Method, SourceAuthority, SourceType,
)

_REF = "https://reference.airopa.internal/illustrative"


def E(signal_id, value, *, unit=None, as_of="2026-01-15", url=_REF,
      stype=SourceType.REFERENCE_DATA, auth=SourceAuthority.SECONDARY,
      conf=0.8, method=Method.LOOKUP, notes=None, inf=None) -> Evidence:
    # Inference signals carry inputs rather than a source URL (Section 7).
    if stype is SourceType.INFERENCE:
        url = None
    return Evidence(
        signal_id=signal_id, value=value, unit=unit, as_of_date=as_of,
        source_url=url, source_type=stype, source_authority=auth,
        confidence=conf, method=method, notes=notes,
        inference_inputs=inf or ([signal_id] if stype is SourceType.INFERENCE else []),
    )


@dataclass
class Seed:
    domain: str
    legal_name: str
    registry_id: str
    jurisdiction: str
    country: str
    sector: str
    revenue: int
    headcount: int
    founding_year: int
    # gate inputs
    entity_exists: object
    india_headcount: object = 0
    tech_titles: list[str] = field(default_factory=list)
    nontech_titles: list[str] = field(default_factory=list)
    it_support: int = 0
    postings: int = 0
    announcement: bool = False
    parent_gcc: bool = False
    nic_codes: list[str] = field(default_factory=list)
    records: int = 30
    ultimate_parent: str | None = None
    subsidiaries: list[dict] = field(default_factory=list)
    state_majority: bool = False
    # extra signals (signal_id -> Evidence)
    signals: list[Evidence] = field(default_factory=list)
    peer_cohort: dict | None = None  # for the public peer headline block


SITE = SourceType.COMPANY_SITE
PRESS = SourceType.PRESS
FILING = SourceType.FILING
JOB = SourceType.JOB_POSTING
PRIMARY = SourceAuthority.PRIMARY


def _standard_signals(sector_market: str) -> list[Evidence]:
    """A rich, scoring set for a STANDARD-mode company (illustrative)."""
    return [
        # Scale
        E("SCALE.02", [720, 760, 810, 850], unit="EURm", stype=FILING, auth=PRIMARY),
        E("SCALE.03", 0.057, unit="cagr", stype=FILING, auth=PRIMARY),
        E("SCALE.05", [3600, 3800, 4000, 4200], unit="people", stype=FILING, auth=PRIMARY),
        E("SCALE.06", [236, 230, 225, 202], unit="EURk per employee", stype=FILING),
        E("SCALE.07", 0.11, unit="share", stype=SITE),
        E("SCALE.09", 14, unit="offices", stype=SITE, auth=PRIMARY),
        E("SCALE.11", 9, unit="legal entities", stype=FILING),
        E("SCALE.13", "division of a larger group", stype=FILING),
        # Scope
        E("SCOPE.01", "SAP ECC (S/4HANA migration in flight)", stype=JOB, auth=PRIMARY),
        E("SCOPE.02", ["Salesforce", "ServiceNow"], stype=JOB),
        E("SCOPE.03", ["Snowflake"], stype=JOB),
        E("SCOPE.05", ["on-premise Oracle"], stype=JOB),
        E("SCOPE.06", False, stype=SITE),
        E("SCOPE.09", True, stype=SITE, auth=PRIMARY,
          notes="Shared services centre in Porto"),
        E("SCOPE.10", True, stype=SourceType.REFERENCE_DATA,
          notes="Design + AMS scope delivered by an external vendor"),
        E("SCOPE.13", ["Group-wide data platform programme (2025)"], stype=PRESS),
        E("SCOPE.15", True, stype=SITE, notes="Public developer portal"),
        E("SCOPE.16", 3, unit="active repos", stype=SourceType.REFERENCE_DATA),
        # Pressure (dated)
        E("PRESS.03", 40_000_000, unit="EUR cost target", as_of="2025-11-02",
          stype=PRESS, auth=PRIMARY, notes="Efficiency programme, FY27 target"),
        E("PRESS.04", "Hiring freeze on corporate functions", as_of="2025-10-05", stype=PRESS),
        E("PRESS.05", True, as_of="2025-09-10", stype=JOB,
          notes="S/4HANA migration in flight; ECC end-of-support exposure"),
        E("PRESS.09", "Bolt-on acquisition requiring integration", as_of="2025-07-20", stype=PRESS),
        E("PRESS.10", "New CIO appointed", as_of="2025-12-01", stype=PRESS),
        E("PRESS.12", "CEO named a delivery bottleneck at capital markets day",
          as_of="2025-10-18", stype=PRESS, auth=PRIMARY),
        E("PRESS.15", ["NIS2", "CSRD"], as_of="2025-06-01", stype=SourceType.REFERENCE_DATA),
        # Executability
        E("EXEC.02", True, stype=SITE, notes="Nearshore delivery from Porto"),
        E("EXEC.03", True, stype=SITE),
        E("EXEC.04", "PE controlled", stype=FILING, auth=PRIMARY),
        E("EXEC.05", [120, 140, 160], unit="EURm cash", stype=FILING),
        E("EXEC.09", True, stype=SITE),
        # Hiring
        E("HIRE.01", 180, unit="open roles", stype=SITE, auth=PRIMARY),
        E("HIRE.03", {"engineering": 60, "commercial": 40, "operations": 80}, stype=SITE),
        E("HIRE.04", 0.33, unit="tech share", stype=SITE),
        E("HIRE.06", 120, unit="days open", stype=SITE, auth=PRIMARY,
          notes="Several engineering roles reposted over 90 days"),
        # India market (reference data — Section 6.2)
        E("DEM.01", {"category": sector_market, "segment": "industrial B2B"}, stype=SITE),
        E("DEM.02", 4_200_000_000, unit="EUR market", notes="India category market"),
        E("DEM.03", 0.14, unit="growth"),
        E("DEM.04", {"gdp_growth": 0.067, "industrial_production": 0.055}, unit="series"),
        E("DEM.05", "industrial B2B"),
        E("DEM.06", "price point meets segment purchasing power"),
        E("DEM.07", "minor localisation required"),
        E("DEM.10", 18_000_000, unit="EUR current India revenue", stype=FILING),
        E("DEM.11", 95_000_000, unit="EUR peer India revenue"),
        E("DEM.12", ["Named Indian buyers exist in the category"]),
        E("DEM.13", 0.12, unit="downstream growth"),
        E("DEM.14", ["Comparable foreign entrant succeeding in category"]),
        E("DEM.15", {"model": "distributors + direct"}, stype=SITE),
        E("DEM.16", {"approval": "BIS certification", "lead_time_months": 6}),
        E("POL.01", True, notes="Sector named in a production-linked incentive"),
        E("POL.02", "automatic", notes="FDI automatic route"),
        E("POL.03", {"state": "Karnataka", "incentive": "capex subsidy"}),
        E("POL.04", {"scheme": "GCC policy applicable"}),
        E("POL.05", {"transfer_pricing": "safe harbour available"}),
        E("POL.06", {"eu_india_fta": "under negotiation"}),
        E("POL.07", "relevant", notes="China-plus-one relevant sector"),
        E("POL.08", ["A named customer relocating production into India (2025)"],
          as_of="2025-08-01", stype=PRESS),
        E("POL.09", ["Government programme names the sector"]),
        # Technology hub (reference + derived)
        Evidence("TAL.01", ["SAP S/4 functional", "test automation", "data engineering"],
                 source_type=SourceType.INFERENCE,
                 inference_inputs=["SCOPE.01", "HIRE.03"], confidence=0.7,
                 method=Method.MODEL, as_of_date="2026-01-15"),
        E("TAL.02", "deep", notes="India depth in required families"),
        E("TAL.03", 0.18, unit="supply growth"),
        E("TAL.04", 85000, unit="relevant graduates/yr"),
        E("TAL.05", "vertical domain experience present in India"),
        E("TAL.06", 6, unit="weeks", notes="India time to fill"),
        E("TAL.07", 20, unit="weeks", stype=SITE, auth=PRIMARY,
          notes="Observed on their own open roles"),
        E("TAL.08", 0.16, unit="attrition", notes="candidate city attrition"),
        E("TAL.09", 28000, unit="EUR india salary benchmark"),
        E("TAL.10", 72000, unit="EUR home salary benchmark"),
        E("TAL.11", "52-61%", notes="Fully loaded cost differential range"),
        E("TAL.12", ["Bengaluru", "Pune"], notes="candidate city shortlist"),
        E("TAL.13", "strong office supply and direct flight links"),
        E("TAL.14", "high English proficiency, workable time zone overlap"),
        E("TAL.15", ["Peers and SIs already deliver this work from India"]),
        E("TAL.16", 140, unit="GCC/SI density in city"),
        E("COST.01", 52_000_000, unit="EUR external IT/eng spend", stype=FILING),
        E("COST.02", {"scope": "AMS + design", "size": "large"}, stype=SourceType.REFERENCE_DATA),
        E("COST.04", 38_000_000, unit="EUR addressable cost base"),
        E("COST.05", "52-61%", notes="Estimated fully loaded saving range"),
        E("COST.07", True, notes="incumbent SI has India delivery capability"),
        E("IPR.30", "high", stype=SourceType.INFERENCE, method=Method.MODEL,
          inf=["IPR.02", "IPR.03"], notes="Derived from R&D + patents"),
        E("IPR.31", "direct", stype=SourceType.INFERENCE, method=Method.MODEL,
          inf=["IPR.10", "IPR.14"]),
        E("IPR.32", True, stype=SourceType.REFERENCE_DATA,
          notes="Current vendor publicly serves sector peers"),
        E("IPR.33", True, stype=SourceType.REFERENCE_DATA),
        E("IPR.34", "high", stype=SourceType.INFERENCE, method=Method.MODEL,
          inf=["IPR.30", "IPR.31"]),
        E("SOV.01", False, stype=FILING),
        E("SOV.02", {"restriction": "none material"}, stype=SourceType.REFERENCE_DATA),
        E("SOV.03", 0.05, unit="share", stype=SITE),
        E("SOV.08", True, notes="GDPR transfer mechanism in place"),
        E("PEER.13", ["engineering", "IT", "shared services"]),
        E("PEER.30", 0.64, unit="penetration", notes="7 of 11 named peers verified"),
    ]


SEEDS: dict[str, Seed] = {
    "nordwind-praezision.de": Seed(
        domain="nordwind-praezision.de",
        legal_name="Nordwind Präzisionstechnik GmbH",
        registry_id="DE-HRB-884120 (illustrative)",
        jurisdiction="Germany", country="DE",
        sector="Precision components manufacturing",
        revenue=850_000_000, headcount=4200, founding_year=1979,
        entity_exists=False, india_headcount=0, records=18,
        ultimate_parent=None,
        peer_cohort={"total": 11, "with_centre": 7, "recent_24m": 3,
                     "aggregate_india_headcount": 2400,
                     "definition": "German precision-components makers, EUR 500m–2bn"},
        signals=_standard_signals("precision industrial components"),
    ),
    "veldhoven-instruments.nl": Seed(
        domain="veldhoven-instruments.nl",
        legal_name="Veldhoven Instruments B.V.",
        registry_id="NL-KVK-34190882 (illustrative)",
        jurisdiction="Netherlands", country="NL",
        sector="Industrial measurement instruments",
        revenue=1_100_000_000, headcount=6100, founding_year=1965,
        entity_exists=True, india_headcount=35, records=28,
        nontech_titles=["Managing Director", "Finance Manager", "HR Business Partner",
                        "Sales Manager", "Logistics Planner", "Accountant",
                        "Country Manager", "Service Technician"],
        subsidiaries=[{"name": "Veldhoven India Pvt Ltd", "country": "IN",
                       "trading_name": "Veldhoven Instruments India"}],
        peer_cohort={"total": 9, "with_centre": 6, "recent_24m": 2,
                     "aggregate_india_headcount": 1850,
                     "definition": "EU measurement-instrument makers, EUR 750m–2bn"},
        signals=_standard_signals("industrial measurement instruments"),
    ),
    "meridiansysteme.de": Seed(
        domain="meridiansysteme.de",
        legal_name="Meridian Systeme AG",
        registry_id="DE-HRB-120994 (illustrative)",
        jurisdiction="Germany", country="DE",
        sector="Industrial automation software",
        revenue=1_600_000_000, headcount=8200, founding_year=1988,
        entity_exists=True, india_headcount=320, records=140, announcement=True,
        tech_titles=["Software Engineer", "Data Engineer", "DevOps Engineer",
                     "Cloud Architect", "QA Automation Engineer", "SAP Consultant"],
        nontech_titles=["Finance Manager", "HR Manager"],
        peer_cohort={"total": 10, "with_centre": 8, "recent_24m": 2,
                     "aggregate_india_headcount": 5200,
                     "definition": "EU automation-software firms, EUR 1–3bn"},
        signals=[
            E("SCALE.02", [1300, 1420, 1510, 1600], unit="EURm", stype=FILING, auth=PRIMARY),
            E("PEER.30", 0.80, unit="penetration", notes="8 of 10 named peers verified"),
            E("PEER.12", 5200, unit="aggregate peer India headcount"),
            E("PEER.13", ["engineering", "R&D", "IT", "shared services"]),
            E("PEER.16", "expanded", notes="Peer centres expanding"),
        ],
    ),
    "kleinwerk-gmbh.de": Seed(
        domain="kleinwerk-gmbh.de",
        legal_name="Kleinwerk GmbH",
        registry_id="DE-HRB-55210 (illustrative)",
        jurisdiction="Germany", country="DE",
        sector="Specialty mechanical components",
        revenue=80_000_000, headcount=380, founding_year=1998,
        entity_exists=False, india_headcount=0, records=12,
        peer_cohort={"total": 8, "with_centre": 4, "recent_24m": 1,
                     "aggregate_india_headcount": 420,
                     "definition": "EU specialty-components makers, EUR 50–150m"},
        signals=[
            E("DEM.02", 900_000_000, unit="EUR market", notes="India category market"),
            E("DEM.03", 0.11, unit="growth"),
            E("DEM.01", {"category": "specialty mechanical components"}, stype=SITE),
        ],
    ),
    "continental-grootverbruik.nl": Seed(
        domain="continental-grootverbruik.nl",
        legal_name="Continental Grootverbruik N.V.",
        registry_id="NL-KVK-24110554 (illustrative)",
        jurisdiction="Netherlands", country="NL",
        sector="Industrial distribution",
        revenue=7_400_000_000, headcount=28000, founding_year=1954,
        entity_exists=True, india_headcount=60, records=26,
        nontech_titles=["Country Manager", "Finance Manager", "Procurement Manager",
                        "Logistics Planner", "Sales Manager", "HR Manager",
                        "Accountant", "Buyer"],
        peer_cohort={"total": 7, "with_centre": 5, "recent_24m": 1,
                     "aggregate_india_headcount": 3100,
                     "definition": "EU industrial distributors, EUR 5–10bn"},
        signals=_standard_signals("industrial distribution"),
    ),
}


def get_seed(domain: str) -> Seed | None:
    d = domain.lower().lstrip("www.")
    for key, seed in SEEDS.items():
        if d == key or d.endswith("." + key) or key in d:
            return seed
    return None


EXAMPLE_DOMAINS = list(SEEDS.keys())
