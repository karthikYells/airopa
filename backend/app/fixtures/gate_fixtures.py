"""Acceptance fixtures for the India gate (Section 11.1).

These are regression fixtures from Airopa's existing manual assessments and
must be re-run after every change to the gate, the dictionary, the reference
data or the scoring weights. The India facts below stand in for what a people
search would resolve; they encode the real historical cases the rule exists for.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.data.evidence import UNKNOWN
from app.data.records import GateVerdict
from app.gate.india_gate import GateInputs
from app.gate.title_classifier import classify_titles


@dataclass
class GateFixture:
    name: str
    expected: GateVerdict
    why: str
    inputs: GateInputs
    # X4 divestment is an exclusion path, not a gate verdict; flagged separately.
    expected_exclusion: str | None = None


def _inputs(
    *,
    entity,
    nic=None,
    headcount=UNKNOWN,
    tech_titles=None,
    nontech_titles=None,
    it_support=0,
    postings=0,
    announcement=False,
    parent_gcc=False,
    records=20,
):
    tech_titles = tech_titles or []
    nontech_titles = nontech_titles or []
    classified = classify_titles(tech_titles + nontech_titles)
    tech_count = sum(1 for c in classified if c.title_class.value == "TECH")
    share = (tech_count / headcount) if isinstance(headcount, int) and headcount else 0.0
    return GateInputs(
        india_entity_exists=entity,
        india_entity_nic_codes=nic or [],
        india_headcount_total=headcount,
        india_tech_role_count=tech_count,
        india_tech_role_share=share,
        india_tech_job_postings_12m=postings,
        public_gcc_announcement=announcement,
        parent_has_india_gcc=parent_gcc,
        gate_evidence_records=records,
        classified_titles=classified,
        it_support_count=it_support,
    )


FIXTURES: list[GateFixture] = [
    GateFixture(
        name="Hettich",
        expected=GateVerdict.CONFIRMED,
        why="Tech roles in India found only via people search, not press/website.",
        inputs=_inputs(
            entity=True, headcount=60, records=40,
            tech_titles=["Software Engineer", "SAP Consultant", "Data Engineer",
                         "DevOps Engineer", "Full Stack Developer", "QA Engineer"],
            nontech_titles=["Finance Manager", "HR Manager"],
        ),
    ),
    GateFixture(
        name="BHS Corrugated",
        expected=GateVerdict.CONFIRMED,
        why="Second case missed by public-source research; people search found IT team.",
        inputs=_inputs(
            entity=True, headcount=45, records=30,
            tech_titles=["Backend Developer", "Cloud Engineer", "Test Engineer",
                         "Embedded Engineer", "Firmware Engineer", "ABAP Developer"],
            nontech_titles=["Sales Manager", "Service Technician"],
        ),
    ),
    GateFixture(
        name="Merck KGaA",
        expected=GateVerdict.CONFIRMED,
        why="Large publicly announced Bengaluru centre — tests the announcement path.",
        inputs=_inputs(
            entity=True, headcount=1500, records=200, announcement=True,
            tech_titles=["Data Scientist", "ML Engineer"],
        ),
    ),
    GateFixture(
        name="Hoermann KG",
        expected=GateVerdict.CLEAR,
        why="India entity since 2012 as 'Shakti Hoermann' with HR/finance/MD but "
            "no tech roles — entity alone does not disqualify.",
        inputs=_inputs(
            entity=True, headcount=40, records=25,
            nontech_titles=["Managing Director", "Finance Manager", "HR Manager",
                            "Accountant", "Sales Manager", "Logistics Planner"],
        ),
    ),
    GateFixture(
        name="Drees und Sommer SE",
        expected=GateVerdict.CLEAR_GREENFIELD,
        why="No India entity, no India staff — greenfield path.",
        inputs=_inputs(entity=False, headcount=0, records=15),
    ),
    GateFixture(
        name="Statkraft",
        expected=GateVerdict.CLEAR_GREENFIELD,  # gate itself; X4 handles the drop
        why="India divestment in 2025 — gate sees no entity; exclusion X4 disqualifies.",
        inputs=_inputs(entity=False, headcount=0, records=15),
        expected_exclusion="X4",
    ),
]
