"""Score B: India Market Opportunity, 100 points (Section 8.2). Public + internal.

The revenue case — is India a market for what they SELL, not only a cost
location? Computed from DEM and POL, keyed to what the company actually sells.

In v1 the India reference dataset (DEM.02/03, POL.*) is not yet licensed, so
those lookups return UNKNOWN and this score typically lands with low coverage.
Per Section 12 that is the correct, honest behaviour — the engine must never
improvise a market size. Public display is then suppressed by the coverage
floor (Section 9.6).
"""
from __future__ import annotations

from app.data.records import CompanyRecord, DimensionScore, ScoreResult
from app.scoring.bands import band_for
from app.scoring.common import clamp, resolved_true, resolved_value
from app.scoring.coverage import confidence_for, coverage_for


def _dim(name: str, max_pts: int, rec: CompanyRecord,
         contributions: list[tuple[str, float]]) -> DimensionScore:
    pts = 0.0
    hit = 0
    for sid, p in contributions:
        v = resolved_value(rec, sid)
        if v in (None, False):
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            pts += p  # presence of a resolved reference figure earns the weight
        else:
            pts += p
        hit += 1
    basis = (f"{hit} resolved signal(s)"
             if hit else "awaiting licensed India reference data")
    return DimensionScore(name, clamp(pts, 0, max_pts), max_pts, basis)


def score_india_market(rec: CompanyRecord, settings) -> ScoreResult:
    dims = [
        _dim("Addressable demand", 25, rec, [
            ("DEM.02", 10), ("DEM.03", 8), ("DEM.13", 4), ("DEM.04", 3)]),
        _dim("Product and segment fit", 20, rec, [
            ("DEM.01", 6), ("DEM.05", 6), ("DEM.06", 5), ("DEM.07", 3)]),
        _dim("Competitive position", 15, rec, [
            ("DEM.11", 6), ("DEM.14", 5), ("DEM.12", 4)]),
        _dim("Policy and incentives", 15, rec, [
            ("POL.01", 4), ("POL.02", 3), ("POL.03", 2), ("POL.04", 2),
            ("POL.05", 1), ("POL.06", 2), ("POL.09", 1)]),
        _dim("Route to market", 15, rec, [
            ("DEM.15", 7), ("DEM.16", 4), ("DEM.09", 4)]),
        _dim("Supply chain and China plus one", 10, rec, [
            ("POL.07", 4), ("POL.08", 6)]),
    ]
    total = clamp(sum(d.points for d in dims), 0, 100)
    cov, resolved, applicable = coverage_for(rec, "india_market")
    conf = confidence_for(rec, "india_market", cov)
    return ScoreResult(
        key="india_market", label="India Market Opportunity", points=total,
        band=band_for(total), coverage=cov, confidence=conf, dimensions=dims,
        applicable_signals=applicable, resolved_signals=resolved,
    )
