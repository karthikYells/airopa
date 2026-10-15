"""Score A: GCC Fit, 100 points (Section 8.1). Internal only — never published.

Four dimensions: Addressable scope (35), Dated pressure (30), Executability
(20), Scale fit (15). Deterministic; every point traces to resolved evidence.
The calibration anchors in Section 8.1 guided the per-signal weights.
"""
from __future__ import annotations

from app.config import Settings
from app.data.records import (
    Band, CompanyRecord, DimensionScore, GateVerdict, ScoreResult,
)
from app.scoring.bands import band_for
from app.scoring.common import (
    clamp, freshness_weight, resolved_true, resolved_value,
)
from app.scoring.coverage import confidence_for, coverage_for


def _scope(rec: CompanyRecord) -> DimensionScore:
    pts = 0.0
    bits: list[str] = []
    # Externalised scope already visible is the strongest earner (Section 5.4).
    if resolved_true(rec, "SCOPE.10"):
        pts += 12; bits.append("named externalised scope")
    if resolved_true(rec, "SCOPE.09"):
        pts += 8; bits.append("existing shared services centre")
    if resolved_value(rec, "SCOPE.01"):
        pts += 5; bits.append("ERP platform identified")
    for sid, p, label in [
        ("SCOPE.02", 2, "enterprise systems"),
        ("SCOPE.03", 2, "modern data stack"),
        ("SCOPE.05", 3, "legacy migration surface"),
        ("SCOPE.06", 2, "ships software"),
        ("SCOPE.13", 3, "announced digital/AI initiative"),
        ("SCOPE.15", 1, "developer portal"),
        ("SCOPE.16", 1, "active GitHub org"),
    ]:
        if resolved_value(rec, sid) not in (None, False):
            pts += p; bits.append(label)
    # Deduct for non-offshorable work (Section 5.4, SCOPE.14).
    nonoff = resolved_value(rec, "SCOPE.14")
    if isinstance(nonoff, (int, float)):
        pts -= min(10, 10 * nonoff); bits.append("non-offshorable deduction")
    basis = ", ".join(bits) if bits else "no named scope resolved"
    return DimensionScore("Addressable scope", clamp(pts, 0, 35), 35, basis)


def _pressure(rec: CompanyRecord) -> DimensionScore:
    pts = 0.0
    dated = 0
    weights = {
        "PRESS.03": 6, "PRESS.05": 6, "PRESS.12": 6, "PRESS.06": 5,
        "PRESS.10": 5, "PRESS.04": 3, "PRESS.07": 3, "PRESS.09": 3,
        "PRESS.11": 3, "PRESS.15": 3, "PRESS.01": 2, "PRESS.02": 2,
        "PRESS.08": 2, "PRESS.13": 2, "PRESS.14": 2, "PRESS.16": 2,
        "PRESS.17": 2, "PRESS.18": 2,
    }
    for sid, w in weights.items():
        ev = rec.get(sid)
        if ev is None or not ev.is_resolved:
            continue
        fw = freshness_weight(ev.as_of_date)
        if fw > 0:
            pts += w * fw
            dated += 1
    basis = (f"{dated} dated event(s), freshness-weighted"
             if dated else "no dated pressure event resolved")
    return DimensionScore("Dated pressure", clamp(pts, 0, 30), 30, basis)


def _executability(rec: CompanyRecord) -> DimensionScore:
    pts = 0.0
    bits: list[str] = []
    # India entity without technology roles is the strongest positive (Section 8.1).
    if rec.gate is not None and rec.gate.verdict is GateVerdict.CLEAR:
        pts += 9; bits.append("India entity exists without tech roles")
    elif rec.gate is not None and rec.gate.verdict is GateVerdict.CLEAR_GREENFIELD:
        pts += 3; bits.append("greenfield (execution risk)")
    if resolved_true(rec, "EXEC.02"):
        pts += 5; bits.append("existing offshore/nearshore delivery")
    if resolved_true(rec, "EXEC.03"):
        pts += 3; bits.append("existing outsourcing relationships")
    conc = resolved_value(rec, "EXEC.04")
    if conc:
        pts += 3; bits.append("concentrated decision")
    if resolved_true(rec, "EXEC.09"):
        pts += 2; bits.append("English working language")
    if resolved_true(rec, "EXEC.11"):
        pts += 2; bits.append("existing India relationship")
    # Deductions.
    if resolved_true(rec, "EXEC.06"):
        pts -= 4; bits.append("works council exposure")
    if resolved_true(rec, "EXEC.12"):
        pts -= 3; bits.append("prior failed offshoring")
    basis = ", ".join(bits) if bits else "no executability evidence resolved"
    return DimensionScore("Executability", clamp(pts, 0, 20), 20, basis)


def _scale(rec: CompanyRecord, s: Settings) -> DimensionScore:
    pts = 0.0
    bits: list[str] = []
    rev = resolved_value(rec, "SCALE.01")
    hc = resolved_value(rec, "SCALE.04")
    if isinstance(rev, (int, float)):
        # Sweet spot ~ EUR 500m–3bn (Section 8.1 anchor).
        if 500_000_000 <= rev <= 3_000_000_000:
            pts += 9; bits.append("revenue in mid-cap sweet spot")
        elif s.x5_revenue_floor_eur <= rev <= s.x6_revenue_ceiling_eur:
            pts += 5; bits.append("revenue within band edge")
    if isinstance(hc, (int, float)):
        if 2000 <= hc <= 15000:
            pts += 6; bits.append("headcount in target range")
        elif hc >= s.x7_headcount_floor:
            pts += 3; bits.append("headcount above floor")
    basis = ", ".join(bits) if bits else "scale not resolved from filings"
    return DimensionScore("Scale fit", clamp(pts, 0, 15), 15, basis)


def score_gcc_fit(rec: CompanyRecord, settings: Settings) -> ScoreResult:
    dims = [_scope(rec), _pressure(rec), _executability(rec), _scale(rec, settings)]
    total = clamp(sum(d.points for d in dims), 0, 100)
    cov, resolved, applicable = coverage_for(rec, "gcc_fit")
    conf = confidence_for(rec, "gcc_fit", cov)
    return ScoreResult(
        key="gcc_fit", label="GCC Fit", points=total, band=band_for(total),
        coverage=cov, confidence=conf, dimensions=dims,
        applicable_signals=applicable, resolved_signals=resolved,
    )
