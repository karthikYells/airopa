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


# Each dimension maps resolved VALUES onto the Section 8.3 calibration anchors.
# Sector benchmarks alone cannot reach the top band where the spec requires the
# company's own evidence (their unfilled roles, their externalised scope).

def _talent(rec: CompanyRecord) -> DimensionScore:
    name, mx = "Talent pool depth for their stack", 25
    depth = resolved_value(rec, "TAL.02")
    if depth is None:
        return DimensionScore(name, 0.0, mx, "not resolved — awaiting talent data")
    pts = {"very_deep": 22.0, "deep": 18.0, "moderate": 11.0, "shallow": 5.0}.get(str(depth), 8.0)
    stack = resolved_value(rec, "TAL.01")
    why = f"India supply {str(depth).replace('_', ' ')} for the sector"
    why += f"; their stack: {', '.join(stack)}" if stack else "; their own stack not identified"
    return DimensionScore(name, pts, mx, why)


def _cost(rec: CompanyRecord) -> DimensionScore:
    name, mx = "Cost arbitrage", 18
    india, home = resolved_value(rec, "TAL.09"), resolved_value(rec, "TAL.10")
    if not isinstance(india, (int, float)) or not isinstance(home, (int, float)) or home <= 0:
        return DimensionScore(name, 0.0, mx, "not resolved — awaiting salary benchmarks")
    saving = (home - india) / home
    externalised = resolved_value(rec, "COST.02") is not None
    if saving > 0.50:
        pts = 17.0 if externalised else 15.0   # 16-18 needs externalised scope too
    elif saving >= 0.35:
        pts = 12.0
    else:
        pts = 7.0
    return DimensionScore(name, pts, mx,
                          f"Indicative fully loaded saving ~{saving:.0%} (sector benchmark)"
                          + ("" if externalised else "; no externalised scope identified"))


def _ip(rec: CompanyRecord) -> DimensionScore:
    """Scores high only where there is real IP AND it is currently exposed
    (Section 8.3). IPR.30 gates the whole dimension."""
    strength = resolved_value(rec, "IPR.30")  # none | moderate | high
    if strength in (None, "none"):
        return DimensionScore("IP control and security", 0.0, 15,
                              "no meaningful IP estate — panel omitted")
    pts, bits = 0.0, []
    ev = rec.get("IPR.30")
    if ev is not None and ev.source_type is not None and ev.source_type.value == "reference_data":
        # Sector IP intensity is not evidence of THIS company's IP estate: cap at
        # the preventative band (4-8) until patents/R&D are resolved for them.
        pts = {"high": 6.0, "moderate": 4.0}.get(str(strength), 2.0)
        return DimensionScore("IP control and security", pts, 15,
                              f"Sector IP intensity {strength}; company patents and "
                              "vendor exposure not yet resolved")
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
    name, mx = "Hiring velocity", 12
    india, home = resolved_value(rec, "TAL.06"), resolved_value(rec, "TAL.07")
    own_open_days = resolved_value(rec, "HIRE.06")  # THEIR roles, observed over time
    if isinstance(own_open_days, (int, float)) and own_open_days >= 90 and isinstance(india, (int, float)):
        return DimensionScore(name, 11.0, mx,
                              f"Their roles open ~{own_open_days:.0f} days vs ~{india} weeks in India")
    if not isinstance(india, (int, float)) or not isinstance(home, (int, float)):
        return DimensionScore(name, 0.0, mx, "not resolved — fill-time data missing")
    gap = home - india
    pts = 8.0 if gap >= 8 else 5.0 if gap >= 4 else 2.0   # no own pain evidenced: max 10
    return DimensionScore(name, pts, mx,
                          f"Sector fill time ~{home} weeks at home vs ~{india} in India; "
                          "their own vacancy duration not yet observed")


def _precedent(rec: CompanyRecord) -> DimensionScore:
    name, mx = "Sector delivery precedent", 12
    prec = resolved_value(rec, "TAL.15")
    if prec is None:
        return DimensionScore(name, 0.0, mx, "not resolved")
    pts = {"strong": 11.0, "adjacent": 8.0, "weak": 4.0, "none": 1.0}.get(str(prec), 4.0)
    return DimensionScore(name, pts, mx, f"Sector precedent for delivery from India: {prec}")


def _sovereignty(rec: CompanyRecord) -> DimensionScore:
    """Starts from full marks and deducts for resolved constraints (Section 8.3)."""
    if not any(rec.get(s) and rec.get(s).is_resolved
               for s in ["SOV.01", "SOV.02", "SOV.03", "SOV.07"]):
        return DimensionScore("Sovereignty and data risk", 0.0, 10,
                              "sovereignty constraints not yet assessed")
    pts, bits = 10.0, []
    if resolved_true(rec, "SOV.01"):
        pts -= 3; bits.append("data residency commitments")
    sov2 = resolved_value(rec, "SOV.02")
    restriction = sov2.get("restriction") if isinstance(sov2, dict) else sov2
    if restriction and str(restriction).lower() not in ("none", "none material"):
        pts -= 3; bits.append(f"sector restriction: {restriction}")
    sov3 = resolved_value(rec, "SOV.03")
    if isinstance(sov3, (int, float)) and sov3 >= 0.10:
        pts -= min(4, 4 * sov3); bits.append(f"defence/sovereign scope ~{sov3:.0%}")
    if resolved_true(rec, "SOV.07"):
        pts -= 2; bits.append("customer consent required")
    basis = ", ".join(bits) if bits else "no material constraints"
    return DimensionScore("Sovereignty and data risk", clamp(pts, 0, 10), 10, basis)


def _location(rec: CompanyRecord) -> DimensionScore:
    name, mx = "Location and infrastructure fit", 8
    cities, attrition = resolved_value(rec, "TAL.12"), resolved_value(rec, "TAL.08")
    if not cities:
        return DimensionScore(name, 0.0, mx, "no city shortlist resolved")
    has_footprint = resolved_value(rec, "GATE.01") is True
    if isinstance(attrition, (int, float)) and attrition <= 0.15 and has_footprint:
        pts = 7.0      # 7-8: clear city, acceptable attrition, existing footprint
    elif isinstance(attrition, (int, float)) and attrition <= 0.18:
        pts = 5.0      # 4-6: defensible city with a trade-off
    else:
        pts = 4.0
    why = f"Candidate cities {', '.join(cities[:3])}"
    if isinstance(attrition, (int, float)):
        why += f"; attrition ~{attrition:.0%}"
    return DimensionScore(name, pts, mx, why)


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
