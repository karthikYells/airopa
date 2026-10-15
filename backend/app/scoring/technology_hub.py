"""Score C: Technology Hub, 100 points (Section 8.3). Public + internal.

The delivery case — can India supply the SPECIFIC capability this company
needs, at a cost and hiring speed that solves a problem they already have?
Computed from TAL, COST, IPR, SOV and PEER. Specificity is the whole value:
a high score must trace to the skill families the company itself cannot fill
(TAL.01), not to a general statement about India's workforce.

As with Score B, the licensed talent/cost reference figures are UNKNOWN in v1,
so coverage is typically low and public display is suppressed by the floor.
The IP-control dimension, however, can resolve from scraped/derived signals.
"""
from __future__ import annotations

from app.data.records import CompanyRecord, DimensionScore, ScoreResult
from app.scoring.bands import band_for
from app.scoring.common import clamp, resolved_true, resolved_value
from app.scoring.coverage import confidence_for, coverage_for


def _talent(rec: CompanyRecord) -> DimensionScore:
    pts, hit = 0.0, 0
    for sid, p in [("TAL.02", 10), ("TAL.03", 5), ("TAL.04", 4), ("TAL.05", 6)]:
        if resolved_value(rec, sid) not in (None, False):
            pts += p; hit += 1
    basis = f"{hit} talent signal(s)" if hit else "awaiting licensed talent data"
    return DimensionScore("Talent pool depth for their stack", clamp(pts, 0, 25), 25, basis)


def _cost(rec: CompanyRecord) -> DimensionScore:
    pts, hit = 0.0, 0
    for sid, p in [("COST.05", 8), ("COST.02", 5), ("COST.04", 3), ("TAL.11", 2)]:
        if resolved_value(rec, sid) not in (None, False):
            pts += p; hit += 1
    basis = f"{hit} cost signal(s)" if hit else "awaiting cost base and benchmarks"
    return DimensionScore("Cost arbitrage", clamp(pts, 0, 18), 18, basis)


def _ip(rec: CompanyRecord) -> DimensionScore:
    """Scores high only where there is real IP AND it is currently exposed
    (Section 8.3). IPR.30 gates the whole dimension."""
    strength = resolved_value(rec, "IPR.30")  # none | moderate | high
    if strength in (None, "none"):
        return DimensionScore("IP control and security", 0.0, 15,
                              "no meaningful IP estate — panel omitted")
    pts, bits = 0.0, []
    base = {"moderate": 5, "high": 8}.get(str(strength), 4)
    pts += base; bits.append(f"IP estate: {strength}")
    exposure = resolved_value(rec, "IPR.31")  # none|indirect|direct|high
    pts += {"high": 7, "direct": 5, "indirect": 3}.get(str(exposure), 0)
    if resolved_true(rec, "IPR.32"):
        pts += 0; bits.append("vendor serves sector peers")
    if resolved_true(rec, "IPR.33"):
        bits.append("already offshore through a vendor")
    basis = ", ".join(bits)
    return DimensionScore("IP control and security", clamp(pts, 0, 15), 15, basis)


def _velocity(rec: CompanyRecord) -> DimensionScore:
    pts, hit = 0.0, 0
    for sid, p in [("TAL.06", 4), ("TAL.07", 4), ("HIRE.06", 4)]:
        if resolved_value(rec, sid) not in (None, False):
            pts += p; hit += 1
    basis = f"{hit} hiring-velocity signal(s)" if hit else "fill-time data not resolved"
    return DimensionScore("Hiring velocity", clamp(pts, 0, 12), 12, basis)


def _precedent(rec: CompanyRecord) -> DimensionScore:
    pts, hit = 0.0, 0
    for sid, p in [("TAL.15", 6), ("PEER.13", 3), ("PEER.30", 3)]:
        if resolved_value(rec, sid) not in (None, False):
            pts += p; hit += 1
    basis = f"{hit} precedent signal(s)" if hit else "no sector delivery precedent resolved"
    return DimensionScore("Sector delivery precedent", clamp(pts, 0, 12), 12, basis)


def _sovereignty(rec: CompanyRecord) -> DimensionScore:
    """Starts from full marks and deducts for resolved constraints (Section 8.3)."""
    if not any(rec.get(s) and rec.get(s).is_resolved
               for s in ["SOV.01", "SOV.02", "SOV.03", "SOV.07"]):
        return DimensionScore("Sovereignty and data risk", 0.0, 10,
                              "sovereignty constraints not yet assessed")
    pts, bits = 10.0, []
    if resolved_true(rec, "SOV.01"):
        pts -= 3; bits.append("data residency commitments")
    if resolved_value(rec, "SOV.02"):
        pts -= 3; bits.append("sector offshore restriction")
    sov3 = resolved_value(rec, "SOV.03")
    if isinstance(sov3, (int, float)):
        pts -= min(4, 4 * sov3); bits.append("defence/sovereign scope")
    if resolved_true(rec, "SOV.07"):
        pts -= 2; bits.append("customer consent required")
    basis = ", ".join(bits) if bits else "no material constraints"
    return DimensionScore("Sovereignty and data risk", clamp(pts, 0, 10), 10, basis)


def _location(rec: CompanyRecord) -> DimensionScore:
    pts, hit = 0.0, 0
    for sid, p in [("TAL.12", 4), ("TAL.13", 2), ("TAL.16", 2)]:
        if resolved_value(rec, sid) not in (None, False):
            pts += p; hit += 1
    basis = f"{hit} location signal(s)" if hit else "no city recommendation resolved"
    return DimensionScore("Location and infrastructure fit", clamp(pts, 0, 8), 8, basis)


def score_technology_hub(rec: CompanyRecord, settings) -> ScoreResult:
    dims = [_talent(rec), _cost(rec), _ip(rec), _velocity(rec),
            _precedent(rec), _sovereignty(rec), _location(rec)]
    total = clamp(sum(d.points for d in dims), 0, 100)
    cov, resolved, applicable = coverage_for(rec, "technology_hub")
    conf = confidence_for(rec, "technology_hub", cov)
    return ScoreResult(
        key="technology_hub", label="Technology Hub Readiness", points=total,
        band=band_for(total), coverage=cov, confidence=conf, dimensions=dims,
        applicable_signals=applicable, resolved_signals=resolved,
    )
