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


def test_strong_sector_gets_six_reasoned_dimensions_with_ranges_only():
    m = _market_insights(_rec("precision_components"), S)
    assert m is not None and m["score"] >= 50
    assert len(m["dimensions"]) == 6
    assert m["headline"] and "Indicative" in m["basis"] and m["why"]
    text = " ".join([m["headline"], m["basis"]] + [d["insight"] for d in m["dimensions"]])
    assert "EUR 10 to 15bn" in text   # the sector market, as a band
    # Figures are shown only as ranges (Section 9.1): strip "N to M" bands and
    # nothing numeric may remain.
    rest = re.sub(r"(EUR )?\d[\d,.]* to \d[\d,.]*(bn|m|%| weeks| months)?", "", text)
    assert not re.search(r"\d", rest), rest


def test_weak_market_makes_no_claim():
    rec = _rec("precision_components")
    rec.india_market.points = 45
    assert _market_insights(rec, S) is None


def test_not_applicable_dimension_is_hidden_not_weak():
    m = _market_insights(_rec("software_saas"), S)
    names = [d["name"] for d in m["dimensions"]]
    assert "Supply chain and China plus one" not in names
    assert len(names) == 5


def test_consumer_goods_fit_reads_moderate_after_review():
    m = _market_insights(_rec("consumer_goods"), S)
    fit = next(d for d in m["dimensions"] if d["name"] == "Product and segment fit")
    assert fit["level"] in ("Moderate", "Strong")


def test_moderate_adaptation_reads_as_variant_needed():
    m = _market_insights(_rec("consumer_goods"), S)
    fit = next(d for d in m["dimensions"] if d["name"] == "Product and segment fit")
    assert fit["level"] == "Moderate" and "variant or price tier" in fit["insight"]
