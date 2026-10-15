"""Exclusions and flags (Section 4).

Run at Tier 1, before any scoring. Each returns a reason code stored on the
record, so a disqualified company can be re-evaluated later if the reason
expires — nothing is deleted; disqualification is a state, not a removal.

Three dispositions: DISQUALIFY removes the record, FLAG continues scoring with
a warning a human must read, CAUTION halts scoring and routes to manual review.

Evaluation order (Section 4): X18, X19, X17, X1, X2, X3, X4, then the remainder.
Stop at the first DISQUALIFY — do not spend on further enrichment.
"""
from __future__ import annotations

from datetime import date

from app.config import Settings
from app.data.evidence import UNKNOWN
from app.data.records import (
    CompanyRecord, Disposition, ExclusionHit, GateVerdict,
)

# Reason codes carry their disposition and human rationale.
_RATIONALE: dict[str, str] = {
    "X1": "India entity exists AND technology roles present — a capability centre already exists.",
    "X2": "Public announcement of a GCC/CoE/R&D/delivery/technology centre in India.",
    "X3": "Ultimate parent runs an India capability centre — the decision sits at group level.",
    "X4": "India operations divested, closed or exited within the last 36 months.",
    "X5": "Revenue below the floor — cannot fund 20–100 FTE plus governance overhead.",
    "X6": "Revenue above the ceiling — very likely already has a captive; review rather than drop.",
    "X7": "Headcount below the floor — too small to carry a separate delivery organisation.",
    "X8": "Majority state/municipal/sovereign ownership — offshore delivery usually prohibited.",
    "X9": "In insolvency, administration, receivership or liquidation — no capex decision available.",
    "X10": "Announced acquisition in progress — decisions frozen until close.",
    "X11": "Published client of adesso — channel partner; approach jointly or not at all.",
    "X12": "Published client of a conflicting SI — judge severity by scope.",
    "X13": "Regulated/sovereign work above threshold — reduces addressable scope sharply.",
    "X14": "Outside target geography.",
    "X15": "Sector on the configured exclusion list.",
    "X16": "Company founded less than the minimum age — no stable scope or governance maturity.",
    "X17": "Already present in Airopa CRM — deduplication, not disqualification on merit.",
    "X18": "Entity resolution failed — never score an unresolved entity.",
    "X19": "India gate returned CAUTION — thin or contradictory India data.",
    "X20": "Signal coverage below the floor after Tier 2 — insufficient evidence for a defensible score.",
}


def _val(rec: CompanyRecord, signal_id: str):
    ev = rec.get(signal_id)
    if ev is None or ev.is_unknown:
        return None
    return ev.value


def evaluate_exclusions(
    rec: CompanyRecord,
    settings: Settings,
    *,
    tier2_coverage: float | None = None,
) -> list[ExclusionHit]:
    """Return every hit, in evaluation order. The caller stops the pipeline at
    the first DISQUALIFY; FLAGs accumulate and travel with the record."""
    hits: list[ExclusionHit] = []

    def hit(code: str, disp: Disposition) -> ExclusionHit:
        return ExclusionHit(code=code, disposition=disp, rationale=_RATIONALE[code])

    # --- cheap dedup / resolution first (Section 4 order) ---
    if rec.resolution_failed or not rec.registry_id:
        hits.append(hit("X18", Disposition.CAUTION))
        return hits  # unresolved: do not evaluate anything else

    if rec.gate is not None and rec.gate.verdict is GateVerdict.CAUTION:
        hits.append(hit("X19", Disposition.CAUTION))
        return hits

    if _val(rec, "CRM.match") is True:
        hits.append(hit("X17", Disposition.DISQUALIFY))
        return hits

    # --- India gate disqualifiers (X1–X4) ---
    if rec.gate is not None and rec.gate.verdict is GateVerdict.CONFIRMED:
        # Distinguish the parent path (X3) from the direct path (X1).
        if _val(rec, "GATE.10") is True:
            hits.append(hit("X3", Disposition.DISQUALIFY))
        else:
            hits.append(hit("X1", Disposition.DISQUALIFY))
        return hits

    if _val(rec, "GATE.09") is True:
        hits.append(hit("X2", Disposition.DISQUALIFY))
        return hits

    if _val(rec, "GATE.11") is True:  # india_divestment_36m
        hits.append(hit("X4", Disposition.DISQUALIFY))
        return hits

    # --- remainder ---
    revenue = _val(rec, "SCALE.01")
    if isinstance(revenue, (int, float)):
        if revenue < settings.x5_revenue_floor_eur:
            hits.append(hit("X5", Disposition.DISQUALIFY))
            return hits
        if revenue > settings.x6_revenue_ceiling_eur:
            hits.append(hit("X6", Disposition.FLAG))  # review, not auto-drop

    headcount = _val(rec, "SCALE.04")
    if isinstance(headcount, (int, float)) and headcount < settings.x7_headcount_floor:
        hits.append(hit("X7", Disposition.DISQUALIFY))
        return hits

    if _val(rec, "OWN.state_majority") is True:
        hits.append(hit("X8", Disposition.DISQUALIFY))
        return hits

    if _val(rec, "FIN.insolvency") is True:
        hits.append(hit("X9", Disposition.DISQUALIFY))
        return hits

    founding_year = _val(rec, "IDENT.08")
    if isinstance(founding_year, int):
        age = date.today().year - founding_year
        if age < settings.x16_min_company_age_years:
            hits.append(hit("X16", Disposition.DISQUALIFY))
            return hits

    country = rec.country
    if country and country not in settings.target_geography_set:
        hits.append(hit("X14", Disposition.DISQUALIFY))
        return hits

    if _val(rec, "SECTOR.excluded") is True:
        hits.append(hit("X15", Disposition.DISQUALIFY))
        return hits

    # --- non-terminal flags (scoring continues) ---
    if _val(rec, "MA.acquisition_in_progress") is True:
        hits.append(hit("X10", Disposition.FLAG))
    if _val(rec, "SI.client_adesso") is True:
        hits.append(hit("X11", Disposition.FLAG))
    if _val(rec, "SI.client_conflict") is True:
        hits.append(hit("X12", Disposition.FLAG))
    if _val(rec, "SOV.03") is not None and isinstance(_val(rec, "SOV.03"), (int, float)):
        if _val(rec, "SOV.03") >= 0.5:  # heavy regulated/sovereign scope
            hits.append(hit("X13", Disposition.FLAG))

    # --- coverage floor after Tier 2 (X20) ---
    if tier2_coverage is not None and tier2_coverage < settings.x20_coverage_floor:
        hits.append(hit("X20", Disposition.CAUTION))

    return hits


def terminal_disposition(hits: list[ExclusionHit]) -> ExclusionHit | None:
    """The first hit that halts the pipeline (DISQUALIFY or CAUTION)."""
    for h in hits:
        if h.disposition in (Disposition.DISQUALIFY, Disposition.CAUTION):
            return h
    return None
