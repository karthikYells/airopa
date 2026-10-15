"""Publication safety (Sections 9.3, 9.6, 11.4).

A public page with a wrong or disclosing figure is published, indexed, and about
a real company — so these are requirements, not suggestions. Two things are
enforced here:

  1. determine_mode(): which response mode a run maps to (Section 9.4).
  2. assert_public_safe(): a hard guard over the final public payload. It is the
     disclosure failure with the highest cost, so it is asserted in code and
     tested. It raises if the payload contains the GCC Fit score (or any
     derivative), or a peer / vendor / individual name.
"""
from __future__ import annotations

from app.config import Settings
from app.data.records import CompanyRecord, GateVerdict, ResponseMode
from app.pipeline.orchestrator import PipelineOutcome

# Keys that must never appear anywhere in a public payload.
_FORBIDDEN_KEYS = {"gcc_fit", "gcc_fit_score", "provisional_gcc_fit",
                   "ranking", "percentile", "registry_id"}


class PublicationSafetyError(AssertionError):
    pass


def determine_mode(outcome: PipelineOutcome, settings: Settings,
                   blocklisted: bool = False) -> ResponseMode:
    rec = outcome.record
    if blocklisted:
        return ResponseMode.EXCLUDED

    # Resolution failure or thin/contradictory data -> honest page.
    if outcome.stopped_at == "Tier 0" or rec.resolution_failed:
        return ResponseMode.INSUFFICIENT_DATA
    if outcome.terminal_code in {"X18", "X19", "X20"}:
        return ResponseMode.INSUFFICIENT_DATA

    # Scale floor -> market-opportunity content only.
    if outcome.terminal_code in {"X5", "X7"}:
        return ResponseMode.SUB_SCALE

    # Existing India capability centre.
    if rec.gate is not None and rec.gate.verdict is GateVerdict.CONFIRMED:
        return ResponseMode.EXISTING_CENTRE
    if outcome.terminal_code in {"X1", "X2", "X3"}:
        return ResponseMode.EXISTING_CENTRE

    # State-owned / sanctioned / client -> generic content, no assessment.
    if outcome.terminal_code in {"X8", "X17"}:
        return ResponseMode.EXCLUDED
    # Other hard disqualifiers that are not a public verdict -> generic content.
    if outcome.terminal_code in {"X9", "X14", "X15", "X16"}:
        return ResponseMode.EXCLUDED

    # Above the upper revenue band -> straight to a person.
    if "X6" in rec.flags:
        return ResponseMode.ENTERPRISE

    # Overall coverage floor (Section 9.6). The public surface rests on the two
    # client-facing scores, so the floor is judged on their best coverage.
    if rec.reached_tier3:
        covs = [s.coverage for s in (rec.india_market, rec.technology_hub) if s]
        if covs and max(covs) < settings.publication_overall_coverage_floor:
            return ResponseMode.INSUFFICIENT_DATA

    return ResponseMode.STANDARD


def _scan(node, path: str = "") -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if str(k).lower() in _FORBIDDEN_KEYS:
                raise PublicationSafetyError(
                    f"forbidden key '{k}' present in public payload at {path}"
                )
            _scan(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _scan(v, f"{path}[{i}]")


def assert_public_safe(payload: dict, forbidden_names: list[str] | None = None) -> dict:
    """Raise if the payload leaks a forbidden key or a named third party.
    Returns the payload unchanged when safe, so callers can wrap in-line."""
    _scan(payload)

    if forbidden_names:
        import json
        blob = json.dumps(payload, default=str).lower()
        for name in forbidden_names:
            n = name.strip().lower()
            if len(n) >= 4 and n in blob:
                raise PublicationSafetyError(
                    f"third-party name '{name}' present in public payload"
                )
    return payload
