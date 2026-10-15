"""India gate acceptance tests (Section 11.1 and 11.4 behavioural criteria)."""
from __future__ import annotations

import pytest

from app.config import get_settings
from app.data.evidence import UNKNOWN
from app.data.records import GateVerdict, TitleClass
from app.fixtures.gate_fixtures import FIXTURES
from app.gate.india_gate import GateInputs, run_gate
from app.gate.title_classifier import classify_one, normalise

S = get_settings()


@pytest.mark.parametrize("fx", FIXTURES, ids=lambda f: f.name)
def test_gate_fixtures(fx):
    result = run_gate(fx.inputs, S)
    assert result.verdict is fx.expected, (
        f"{fx.name}: expected {fx.expected}, got {result.verdict} "
        f"({result.reason})"
    )


def test_caution_on_thin_data():
    """A company with fewer than 10 India records returns CAUTION (Section 11.4)."""
    inp = GateInputs(
        india_entity_exists=True, india_entity_nic_codes=[],
        india_headcount_total=5, india_tech_role_count=0,
        india_tech_role_share=0.0, india_tech_job_postings_12m=0,
        public_gcc_announcement=False, parent_has_india_gcc=False,
        gate_evidence_records=4, classified_titles=[], it_support_count=0,
    )
    assert run_gate(inp, S).verdict is GateVerdict.CAUTION


def test_it_support_only_is_clear_not_confirmed():
    """Only IT-support titles -> CLEAR, not CONFIRMED (Section 3.3 / 11.4)."""
    titles = classify_titles = None  # noqa
    from app.gate.title_classifier import classify_titles
    classified = classify_titles(["IT Support", "Helpdesk Analyst", "Desktop Support"])
    inp = GateInputs(
        india_entity_exists=True, india_entity_nic_codes=[],
        india_headcount_total=20, india_tech_role_count=0,
        india_tech_role_share=0.0, india_tech_job_postings_12m=0,
        public_gcc_announcement=False, parent_has_india_gcc=False,
        gate_evidence_records=20, classified_titles=classified,
        it_support_count=3,
    )
    assert run_gate(inp, S).verdict is GateVerdict.CLEAR


def test_large_it_support_escalates_to_caution():
    from app.gate.title_classifier import classify_titles
    classified = classify_titles(["IT Support"] * 20)
    inp = GateInputs(
        india_entity_exists=True, india_entity_nic_codes=[],
        india_headcount_total=30, india_tech_role_count=0,
        india_tech_role_share=0.0, india_tech_job_postings_12m=0,
        public_gcc_announcement=False, parent_has_india_gcc=False,
        gate_evidence_records=30, classified_titles=classified,
        it_support_count=20,
    )
    assert run_gate(inp, S).verdict is GateVerdict.CAUTION


def test_unknown_entity_is_caution_not_zero():
    inp = GateInputs(
        india_entity_exists=UNKNOWN, india_entity_nic_codes=[],
        india_headcount_total=UNKNOWN, india_tech_role_count=0,
        india_tech_role_share=0.0, india_tech_job_postings_12m=0,
        public_gcc_announcement=False, parent_has_india_gcc=False,
        gate_evidence_records=50, classified_titles=[], it_support_count=0,
    )
    assert run_gate(inp, S).verdict is GateVerdict.CAUTION


def test_nic_code_path_confirms():
    inp = GateInputs(
        india_entity_exists=True, india_entity_nic_codes=["6201"],
        india_headcount_total=12, india_tech_role_count=0,
        india_tech_role_share=0.0, india_tech_job_postings_12m=0,
        public_gcc_announcement=False, parent_has_india_gcc=False,
        gate_evidence_records=20, classified_titles=[], it_support_count=0,
    )
    assert run_gate(inp, S).verdict is GateVerdict.CONFIRMED


def test_normalisation_preserves_qualifying_noun():
    assert normalise("Senior Manufacturing Engineer") == "manufacturing engineer"
    assert normalise("Sr. Software Engineer II") == "software engineer"


def test_classifier_separates_plant_from_software():
    assert classify_one("Manufacturing Engineer").title_class is TitleClass.NON_TECH
    assert classify_one("Software Engineer").title_class is TitleClass.TECH
    assert classify_one("Sales Engineer").title_class is TitleClass.NON_TECH
    assert classify_one("Engineer").title_class is TitleClass.AMBIGUOUS


def test_reproducibility_of_classification():
    a = [c.title_class for c in __import__(
        "app.gate.title_classifier", fromlist=["classify_titles"]
    ).classify_titles(["Data Engineer", "Engineer", "Buyer"])]
    b = [c.title_class for c in __import__(
        "app.gate.title_classifier", fromlist=["classify_titles"]
    ).classify_titles(["Data Engineer", "Engineer", "Buyer"])]
    assert a == b
