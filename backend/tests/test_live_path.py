"""Live-path acceptance (offline): sector classification + India reference
dataset drive the two public scores for any company, without network."""
from __future__ import annotations

from app.adapters.web_scraper import ScrapeResult
from app.adapters.wikidata import WikidataEntity
from app.config import get_settings
from app.data.records import CompanyRecord, GateVerdict
from app.gate.india_gate import run_gate
from app.reference.india_reference import lookup
from app.scoring.coverage import coverage_for
from app.scoring.india_market import score_india_market
from app.scoring.technology_hub import score_technology_hub
from app.signals.collect import collect_live, country_code
from app.signals.sector import classify_sector

S = get_settings()


def test_sector_classifier_maps_known_text():
    key, conf, method = classify_sector(
        "We are a precision components manufacturer making machined parts, "
        "fasteners and bearings for industrial customers.")
    assert key == "precision_components"
    assert conf > 0.4


def test_sector_classifier_unresolved_is_graceful():
    key, conf, method = classify_sector("Welcome to our website.")
    assert key is None and method == "unresolved"


def test_country_code_mapping():
    assert country_code("Germany") == "DE"
    assert country_code("United Kingdom") == "UK"
    assert country_code("Sweden") == "Nordics"
    assert country_code("Japan") is None


def _synthetic(sector_key="industrial_machinery", india_office=False):
    rec = CompanyRecord(input_url="example.de")
    rec.country = "DE"
    sr = ScrapeResult(
        input_url="example.de", resolved_host="example.de", reachable=True,
        pages_fetched=["https://example.de"], homepage_text="machine building",
        india_checks=5, india_office_detected=india_office,
        india_pages=["https://example.de/locations"] if india_office else [],
    )
    wd = WikidataEntity(found=True, qid="Q1", label="Example GmbH",
                        country="Germany", industry="machinery",
                        inception_year=1970, india_subsidiary=india_office)
    ref = lookup(sector_key)
    rec.sector = ref.sector
    gi = collect_live(rec, sr, wd, ref, S)
    return rec, gi


def test_live_path_public_scores_clear_floor():
    """The two public scores resolve above the 55% publication floor for any
    classified company, from the reference dataset alone."""
    rec, _ = _synthetic()
    rec.india_market = score_india_market(rec, S)
    rec.technology_hub = score_technology_hub(rec, S)
    assert rec.india_market.coverage >= S.publication_score_coverage_floor
    assert rec.technology_hub.coverage >= S.publication_score_coverage_floor
    assert rec.india_market.points > 0
    assert rec.technology_hub.points > 0


def test_live_gate_greenfield_when_no_india():
    rec, gi = _synthetic(india_office=False)
    assert run_gate(gi, S).verdict is GateVerdict.CLEAR_GREENFIELD


def test_live_gate_clear_when_india_entity_no_tech():
    rec, gi = _synthetic(india_office=True)
    # India entity detected, no tech titles scraped -> CLEAR (ideal profile).
    assert run_gate(gi, S).verdict is GateVerdict.CLEAR


def test_reference_consistency_same_sector():
    a = lookup("software_saas")
    b = lookup("software_saas")
    assert a.market_size_eur == b.market_size_eur  # consistent per sector


def test_model_decides_sector_over_customer_keywords():
    class FakeLLM:
        enabled = True
        def classify_sector(self, text, keys, name=None, industry=None):
            return "industrial_machinery"
    # Keyword counting alone would say food_beverage.
    text = "Packaging machines for the food industry: bakery, biscuits, food, food."
    assert classify_sector(text)[0] == "food_beverage"
    key, conf, method = classify_sector(text, llm=FakeLLM(), name="Royal Houdijk")
    assert (key, method) == ("industrial_machinery", "model")
