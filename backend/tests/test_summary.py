"""The short version: built only from facts on the page, silent when thin."""
from __future__ import annotations

from app.data.records import CompanyRecord, GateResult, GateVerdict
from app.narrative.summary import build_summary


def _rec(verdict, financials=None):
    rec = CompanyRecord(input_url="example.nl")
    rec.sector = "Precision components"
    rec.gate = GateResult(verdict=verdict, tech_present=False, title_mix={}, classified_titles=[], reason="")
    rec.financials = financials
    return rec


FIN = {"year": 2025, "op_margin": 0.084, "op_margin_prev": 0.093, "revenue_growth": -0.018}
PEER = {"with_centre": 8, "total": 14}


def test_peers_ahead_and_greenfield_is_sharp_and_factual():
    s = build_summary(_rec(GateVerdict.CLEAR_GREENFIELD, FIN), PEER)
    assert s["headline"] == "Most of your closest peers already build in India. You do not, yet."
    assert "8 of your 14 closest European peers" in s["body"]
    assert "fell from 9.3% to 8.4% in FY2025, on revenue down 1.8%" in s["body"]
    assert "no presence there today" in s["body"] and "compounds" in s["close"]


def test_entity_without_tech_team():
    s = build_summary(_rec(GateVerdict.CLEAR, FIN), PEER)
    assert "entity there, but no team" in s["headline"]
    assert "slowest part of setting up is done" in s["body"]


def test_too_little_to_say_is_silent():
    assert build_summary(_rec(GateVerdict.CAUTION), None) is None


def test_no_peer_in_india_is_a_first_mover_message():
    s = build_summary(_rec(GateVerdict.CLEAR_GREENFIELD, FIN), {"with_centre": 0, "total": 14})
    assert s["headline"].startswith("None of your closest peers has a team in India yet")
    assert "None of your 14 closest European peers" in s["body"] and "still yours" in s["close"]
