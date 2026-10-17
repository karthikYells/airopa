"""Public reasoning per dimension and the indicative scale: ranges only,
company facts where known, nothing where a signal is missing."""
from __future__ import annotations

import re

from app.config import get_settings
from app.data.evidence import Evidence, Method, SourceType
from app.data.records import CompanyRecord
from app.narrative.public_snapshot import _tech_hub_card
from app.narrative.reasoning import eur_range, indicative_scale, pct_range, weeks_range
from app.reference.india_reference import lookup
from app.scoring.technology_hub import score_technology_hub
from app.signals.collect import _apply_reference

S = get_settings()
RANGE = r"(EUR )?\d[\d,.]* to \d[\d,.]*(bn|m|%| weeks| months| people)?|over \d[\d,]*"


def _rec(headcount: int | None = 3400) -> CompanyRecord:
    rec = CompanyRecord(input_url="example.nl")
    ref = lookup("precision_components")
    rec.sector, rec.jurisdiction = ref.sector, "Netherlands"
    _apply_reference(rec, ref)
    if headcount:
        rec.add(Evidence("SCALE.04", headcount, unit="people", source_url="https://example.nl",
                         source_type=SourceType.COMPANY_SITE, confidence=0.7, method=Method.PARSER,
                         as_of_date="2026-10-01"))
    rec.technology_hub = score_technology_hub(rec, S)
    return rec


def test_range_helpers():
    assert pct_range(0.12) == "10 to 15%" and pct_range(0.66, 10) == "60 to 70%"
    assert eur_range(12e9) == "EUR 10 to 15bn" and eur_range(3.2e9) == "EUR 3 to 4bn"
    assert eur_range(450e6) == "EUR 400 to 500m" and weeks_range(6) == "4 to 6 weeks"


def test_tech_hub_reasons_are_specific_and_ranged():
    card = _tech_hub_card(_rec(), S)
    assert card is not None
    by = {d["name"]: d["reason"] for d in card["dimensions"]}
    assert "the Netherlands" in by["Cost arbitrage"] and "%" in by["Cost arbitrage"]
    assert "weeks" in by["Hiring velocity"]
    text = " ".join(by.values())
    assert not re.search(r"\d", re.sub(RANGE, "", text)), "figures only as ranges"


def test_indicative_scale_from_headcount_and_benchmark():
    sc = indicative_scale(_rec(3400))
    assert sc["first_phase_team"] == "20 to 35 people"
    assert re.fullmatch(r"\d0 to \d0%", sc["indicative_saving"])
    assert sc["time_to_first_team_live"] == "4 to 6 months"   # no India entity
    assert "not an offer" in sc["note"]


def test_no_headcount_no_scale():
    assert indicative_scale(_rec(None)) is None
