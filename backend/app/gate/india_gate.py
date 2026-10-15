"""The India gate — the primary disqualification rule (Section 3).

Deterministic. No model may run here. It overrides every other signal. The rule
in one sentence: a company that already has an India entity AND has technology
roles staffed in India is DISQUALIFIED. An India entity on its own is NOT
disqualifying — it is a positive signal, because it removes entity setup risk.

Implemented exactly as the Section 3.2 pseudocode, with the Section 3.3
counterweights layered on (IT-support-only, IT-support escalation, ambiguous
>40% CAUTION).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.config import Settings
from app.data.evidence import UNKNOWN
from app.data.records import ClassifiedTitle, GateResult, GateVerdict, TitleClass
from app.gate.title_classifier import title_mix


@dataclass
class GateInputs:
    """GATE.01 - GATE.12 (Section 3.2). UNKNOWN is never treated as zero."""
    india_entity_exists: object           # GATE.01: True | False | UNKNOWN
    india_entity_nic_codes: list[str]     # GATE.03
    india_headcount_total: object         # GATE.04: int | UNKNOWN
    india_tech_role_count: int            # GATE.06 (derived from classification)
    india_tech_role_share: float          # GATE.07 (GATE.06 / GATE.04)
    india_tech_job_postings_12m: int      # GATE.08
    public_gcc_announcement: bool         # GATE.09
    parent_has_india_gcc: bool            # GATE.10
    gate_evidence_records: int            # GATE.12
    classified_titles: list[ClassifiedTitle] = field(default_factory=list)
    it_support_count: int = 0             # Section 3.3 local-IT carve-out
    # Live crawls examine fewer but targeted India sources than a people search;
    # this lowers the thin-data floor only on that path (None = use the default).
    min_records_override: int | None = None


def _tech_present(g: GateInputs, s: Settings) -> bool:
    """Step 2. Any one path is sufficient (Section 3.2)."""
    share_path = (
        g.india_tech_role_share >= s.gate_tech_role_share_min
        and isinstance(g.india_headcount_total, int)
        and g.india_headcount_total >= s.gate_tech_role_share_headcount_min
    )
    return bool(
        g.india_tech_role_count >= s.gate_tech_role_count_min
        or share_path
        or g.india_tech_job_postings_12m >= 1
        or g.public_gcc_announcement is True
        or any(c.startswith(("62", "63")) for c in g.india_entity_nic_codes)
    )


def run_gate(g: GateInputs, settings: Settings) -> GateResult:
    mix = title_mix(g.classified_titles)
    tech_present = _tech_present(g, settings)

    def result(verdict: GateVerdict, reason: str) -> GateResult:
        return GateResult(verdict=verdict, tech_present=tech_present,
                          title_mix=mix, classified_titles=g.classified_titles,
                          reason=reason)

    # Step 1. Insufficient-data check runs first (Section 3.2).
    min_records = (g.min_records_override if g.min_records_override is not None
                   else settings.gate_min_evidence_records)
    if g.india_entity_exists is UNKNOWN or g.gate_evidence_records < min_records:
        return result(GateVerdict.CAUTION,
                      "Insufficient India data: entity existence unknown or "
                      f"fewer than {min_records} records.")

    # Section 3.3 counterweight: ambiguous titles over the share cap -> CAUTION,
    # regardless of counts, so a borderline mix reaches a human.
    if mix["total"] and mix["shares"][TitleClass.AMBIGUOUS.value] > settings.gate_ambiguous_share_caution:
        return result(GateVerdict.CAUTION,
                      "Ambiguous titles exceed "
                      f"{int(settings.gate_ambiguous_share_caution * 100)}% of the "
                      "India title mix.")

    # Section 3.3 counterweight: a large shared service desk (IT support > N)
    # is not site support -> escalate for manual review.
    if g.it_support_count > settings.gate_it_support_escalate:
        return result(GateVerdict.CAUTION,
                      f"IT-support headcount ({g.it_support_count}) exceeds "
                      f"{settings.gate_it_support_escalate}: likely a shared "
                      "service desk, not site support.")

    # Step 3. Parent override — the decision sits at group level (Section 3.2).
    if g.parent_has_india_gcc is True:
        return result(GateVerdict.CONFIRMED,
                      "Ultimate parent runs an India capability centre.")

    # Step 4. Main decision (Section 3.2 truth table).
    if g.india_entity_exists is True and tech_present:
        return result(GateVerdict.CONFIRMED,
                      "India entity exists AND technology roles present.")
    if g.india_entity_exists is True and not tech_present:
        return result(GateVerdict.CLEAR,
                      "India entity exists with no technology roles — ideal "
                      "profile, entity risk already removed.")
    if g.india_entity_exists is False and tech_present:
        return result(GateVerdict.CAUTION,
                      "No India entity but technology roles present — anomalous "
                      "(contractors, unconsolidated acquisition, or resolution error).")
    return result(GateVerdict.CLEAR_GREENFIELD,
                  "No India entity and no India technology roles — greenfield.")
