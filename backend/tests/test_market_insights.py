"""Market access view on the public page: words only, labelled indicative,
and no market claim at all when the market is weak (Sections 8.4, 8.5)."""
from __future__ import annotations

import re

from app.config import get_settings
from app.data.records import CompanyRecord
from app.narrative.public_snapshot import _market_insights
from app.reference.india_reference import lookup
from app.scoring.india_market import score_india_market
from app.signals.collect import _apply_reference

S = get_settings()


def _rec(sector_key: str) -> CompanyRecord:
    rec = CompanyRecord(input_url="example.de")
    ref = lookup(sector_key)
    rec.sector = ref.sector
    _apply_reference(rec, ref)
    rec.india_market = score_india_market(rec, S)
    return rec


def test_strong_sector_gets_six_worded_dimensions_without_figures():
    m = _market_insights(_rec("precision_components"), S)
    assert m is not None and m["score"] >= 50
    assert len(m["dimensions"]) == 6
    assert m["headline"] and "Indicative" in m["basis"]
    text = " ".join([m["headline"], m["basis"]] + [d["insight"] for d in m["dimensions"]])
    assert not re.search(r"\d|EUR|%", text), "raw reference figures must stay internal"


def test_weak_market_makes_no_claim():
    rec = _rec("precision_components")
    rec.india_market.points = 45
    assert _market_insights(rec, S) is None
