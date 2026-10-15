"""End-to-end pipeline + public-safety acceptance (Sections 9, 11.4)."""
from __future__ import annotations

import pytest

from app.api.abuse import is_blocklisted, validate
from app.config import get_settings
from app.data.records import ResponseMode
from app.narrative.internal_brief import build_brief
from app.narrative.public_snapshot import build_snapshot
from app.narrative.safety import (
    PublicationSafetyError, assert_public_safe, determine_mode,
)
from app.pipeline.orchestrator import run_pipeline

S = get_settings()


def _public(host, blocklisted=False):
    outcome = run_pipeline(host, S, surface="public")
    mode = determine_mode(outcome, S, blocklisted=blocklisted)
    from app.fixtures.demo_companies import get_seed
    seed = get_seed(host)
    payload = build_snapshot(outcome, S, mode, seed_cohort=seed.peer_cohort if seed else None)
    return outcome, mode, payload


def test_standard_company_three_scores_internal():
    outcome = run_pipeline("nordwind-praezision.de", S, surface="internal")
    rec = outcome.record
    assert rec.reached_tier3
    assert rec.gcc_fit and rec.india_market and rec.technology_hub
    assert rec.narrative_mode in {"DUAL", "COST_LED", "COST_ONLY"}


def test_public_payload_never_contains_gcc_fit():
    _, mode, payload = _public("nordwind-praezision.de")
    assert mode in {ResponseMode.STANDARD, ResponseMode.EXISTING_CENTRE}
    # Must not raise — and explicitly check the forbidden key is absent.
    assert_public_safe(payload)
    import json
    assert "gcc_fit" not in json.dumps(payload).lower()


def test_safety_guard_catches_leak():
    with pytest.raises(PublicationSafetyError):
        assert_public_safe({"ok": 1, "gcc_fit": 84})


def test_safety_guard_catches_named_peer():
    with pytest.raises(PublicationSafetyError):
        assert_public_safe({"peer": "Veldhoven Instruments"},
                           forbidden_names=["Veldhoven Instruments"])


def test_existing_centre_mode_never_says_disqualified():
    _, mode, payload = _public("meridiansysteme.de")
    assert mode is ResponseMode.EXISTING_CENTRE
    import json
    blob = json.dumps(payload).lower()
    assert "disqualif" not in blob
    assert "nothing to gain" not in blob


def test_sub_scale_mode():
    _, mode, payload = _public("kleinwerk-gmbh.de")
    assert mode is ResponseMode.SUB_SCALE
    assert payload["lead_capture"]["type"] == "sector_briefing"


def test_enterprise_mode_routes_to_person():
    _, mode, payload = _public("continental-grootverbruik.nl")
    assert mode is ResponseMode.ENTERPRISE
    assert payload["lead_capture"]["type"] == "route_to_partner"


def test_blocklisted_is_excluded():
    _, mode, payload = _public("adesso.de", blocklisted=True)
    assert mode is ResponseMode.EXCLUDED
    assert payload["lead_capture"] is None


def test_delivery_gate_caps_gcc_fit():
    """Rule 1 (Section 8.5): technology_hub < 50 caps GCC Fit at 60 + flag."""
    outcome = run_pipeline("nordwind-praezision.de", S, surface="internal")
    rec = outcome.record
    if rec.technology_hub.points < 50:
        assert rec.gcc_fit.points <= 60
        assert "DELIVERY_CASE_WEAK" in rec.flags


def test_cost_only_mode_has_no_market_claim():
    outcome = run_pipeline("nordwind-praezision.de", S, surface="internal")
    rec = outcome.record
    if rec.narrative_mode == "COST_ONLY":
        brief = build_brief(outcome, S)
        assert brief["scores"]["india_market"]["score"] < 45


def test_free_email_rejected():
    ok, _, reason = validate("someone@gmail.com")
    assert not ok and reason == "free_email_provider"


def test_internal_brief_has_gcc_fit_and_sources():
    outcome = run_pipeline("nordwind-praezision.de", S, surface="internal")
    brief = build_brief(outcome, S)
    assert brief["scores"]["gcc_fit"] is not None
    assert isinstance(brief["source_urls"], list)


def test_reproducibility_same_scores_twice():
    a = run_pipeline("veldhoven-instruments.nl", S, surface="internal").record
    b = run_pipeline("veldhoven-instruments.nl", S, surface="internal").record
    assert a.gcc_fit.points == b.gcc_fit.points
    assert a.technology_hub.points == b.technology_hub.points
