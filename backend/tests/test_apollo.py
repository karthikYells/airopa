"""Apollo adapter + live-path gate wiring (offline, no network, no credits)."""
from __future__ import annotations

from app.adapters.apollo import (
    ApolloResult, normalise_domain, parse_india_postings, parse_org, parse_people,
)
from app.adapters.web_scraper import ScrapeResult
from app.adapters.wikidata import WikidataEntity
from app.config import get_settings
from app.data.records import CompanyRecord, GateVerdict
from app.gate.india_gate import run_gate
from app.reference.india_reference import lookup
from app.signals.collect import collect_live

S = get_settings()


def test_normalise_domain():
    assert normalise_domain("www.Example.de") == "example.de"
    assert normalise_domain("example.de/careers") == "example.de"


def test_parse_people_reads_total_and_titles():
    total, titles = parse_people({"total_entries": 3192, "people": [
        {"title": "Software Engineer II"}, {"title": " "}, {"title": "Finance Manager"}]})
    assert total == 3192
    assert titles == ["Software Engineer II", "Finance Manager"]


def test_parse_people_pagination_fallback():
    total, _ = parse_people({"pagination": {"total_entries": 7}, "people": []})
    assert total == 7


def test_parse_org_converts_revenue_to_eur():
    org = parse_org({"organization": {"id": "abc", "name": "Example GmbH",
                                      "annual_revenue": 1_000_000_000,
                                      "estimated_num_employees": 4200}})
    assert org["org_id"] == "abc" and org["employees"] == 4200
    assert org["revenue_eur"] == 920_000_000


def test_parse_india_postings_filters_location():
    titles = parse_india_postings({"organization_job_postings": [
        {"title": "Data Engineer", "city": "Bengaluru", "country": "India"},
        {"title": "Sales Manager", "city": "Munich", "country": "Germany"}]})
    assert titles == ["Data Engineer"]


def _run(apollo: ApolloResult):
    rec = CompanyRecord(input_url="example.de")
    rec.country = "DE"
    # A crawl whose "careers titles" are nav menu text — the failure Apollo fixes.
    sr = ScrapeResult(input_url="example.de", resolved_host="example.de", reachable=True,
                      pages_fetched=["https://example.de"], homepage_text="machine building",
                      india_checks=3, india_careers_titles=["Find a Store", "Sign In", "Help"])
    wd = WikidataEntity(found=True, qid="Q1", label="Example GmbH", country="Germany")
    ref = lookup("industrial_machinery")
    rec.sector = ref.sector
    return rec, collect_live(rec, sr, wd, ref, S, apollo=apollo)


def test_apollo_india_tech_staff_confirms_existing_centre():
    ap = ApolloResult(found=True, domain="example.de", india_people_count=250,
                      india_titles=["Software Engineer"] * 8 + ["Data Engineer"] * 4
                      + ["Finance Manager"] * 2)
    rec, gi = _run(ap)
    assert gi.india_headcount_total == 250
    assert rec.get("GATE.04").value == 250
    assert run_gate(gi, S).verdict is GateVerdict.CONFIRMED


def test_apollo_no_india_people_is_greenfield():
    ap = ApolloResult(found=True, domain="example.de", org_id="abc", india_people_count=0)
    rec, gi = _run(ap)
    assert rec.get("GATE.01").value is False
    assert run_gate(gi, S).verdict is GateVerdict.CLEAR_GREENFIELD


def test_apollo_fills_scale_only_when_wikidata_missing():
    ap = ApolloResult(found=True, domain="example.de", org_id="abc",
                      employees=4200, revenue_eur=920_000_000, founded_year=1950)
    rec, _ = _run(ap)
    assert rec.get("SCALE.04").value == 4200
    assert rec.get("SCALE.01").value == 920_000_000
    assert "Apollo" in (rec.get("SCALE.04").notes or "")


def test_sap_qualified_titles_are_tech():
    from app.gate.title_classifier import classify_one
    for t in ["SAP EWM Consultant", "SAP Functional Consultant",
              "Sap Advanced Business Application Programming Consultant"]:
        assert classify_one(t).title_class.value == "TECH", t
    assert classify_one("SAP Sales Manager").title_class.value == "NON_TECH"


def test_batch_sends_ambiguous_and_misses_to_model_once():
    from app.data.records import TitleClass
    from app.gate.title_classifier import classify_titles

    class FakeLLM:
        enabled = True
        calls = []

        def classify_titles_batch(self, titles, context=None):
            self.calls.append(list(titles))
            return {t: (TitleClass.TECH, 0.8) for t in titles}

    llm = FakeLLM()
    out = classify_titles(["Software Engineer", "Consultant", "Process Associate"], llm=llm)
    assert llm.calls == [["Consultant", "Process Associate"]]  # one batch, dictionary hits skipped
    assert [c.method for c in out] == ["dictionary", "model", "model"]


def test_few_india_profiles_are_not_an_entity():
    # Kramp-like: 4 non-tech people in India is not an India entity.
    ap = ApolloResult(found=True, domain="example.de", india_people_count=4,
                      india_titles=["Sales Manager", "Account Manager", "Area Sales Manager",
                                    "Key Account Manager"])
    rec, gi = _run(ap)
    assert rec.get("GATE.01").value is False
    assert run_gate(gi, S).verdict is GateVerdict.CLEAR_GREENFIELD


def test_few_india_profiles_with_tech_go_to_review():
    ap = ApolloResult(found=True, domain="example.de", india_people_count=6,
                      india_titles=["Software Engineer"] * 5 + ["Sales Manager"])
    _, gi = _run(ap)
    assert run_gate(gi, S).verdict is GateVerdict.CAUTION  # no entity but tech: a human looks


def test_parse_org_name_majority():
    from app.adapters.apollo import parse_org_name
    data = {"people": [{"organization": {"name": "Etex"}}, {"organization": {"name": "Etex"}},
                       {"organization": {"name": "Etex Building Performance"}}, {}]}
    assert parse_org_name(data) == "Etex"


def test_apollo_evidence_dated_when_queried():
    import time
    ap = ApolloResult(found=True, domain="example.de", india_people_count=250,
                      india_titles=["Software Engineer"] * 8,
                      fetched_at=time.mktime((2026, 9, 1, 12, 0, 0, 0, 0, -1)))
    rec, _ = _run(ap)
    assert rec.get("GATE.04").as_of_date == "2026-09-01"


def test_ambiguous_rule_ignores_tiny_samples():
    # Etex-like: 2 India profiles, 1 unclear title -> not "50% ambiguous".
    ap = ApolloResult(found=True, domain="example.de", india_people_count=2,
                      india_titles=["Sales Manager", "Associate"])
    _, gi = _run(ap)
    assert run_gate(gi, S).verdict is GateVerdict.CLEAR_GREENFIELD


def test_leadership_change_becomes_dated_pressure_but_no_change_does_not():
    from app.scoring.gcc_fit import score_gcc_fit
    yes = ApolloResult(found=True, domain="example.de", org_id="abc", leadership_checked=True,
                       new_tech_leaders=["CIO"], fetched_at=__import__("time").time())
    rec, _ = _run(yes)
    assert rec.get("PRESS.10").value is True and "CIO" in rec.get("PRESS.10").notes
    pressure_yes = next(d for d in score_gcc_fit(rec, S).dimensions if d.name == "Dated pressure").points

    no = ApolloResult(found=True, domain="example.de", org_id="abc", leadership_checked=True,
                      fetched_at=__import__("time").time())
    rec2, _ = _run(no)
    assert rec2.get("PRESS.10").value is False
    pressure_no = next(d for d in score_gcc_fit(rec2, S).dimensions if d.name == "Dated pressure").points
    assert pressure_yes > pressure_no == 0
