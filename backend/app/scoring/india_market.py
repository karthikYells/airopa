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
from app.scoring.common import clamp, resolved_value
from app.scoring.coverage import confidence_for, coverage_for


# Each dimension maps the resolved VALUES onto the Section 8.2 calibration
# anchors. A value earns the band it evidences — a flat, small market does not
# score like a large, fast-growing one. UNKNOWN inputs score 0 and say so.

def _unknown(name: str, max_pts: int) -> DimensionScore:
    return DimensionScore(name, 0.0, max_pts, "not resolved — awaiting reference data")


def _demand(rec: CompanyRecord) -> DimensionScore:
    name, mx = "Addressable demand", 25
    size, growth = resolved_value(rec, "DEM.02"), resolved_value(rec, "DEM.03")
    down = resolved_value(rec, "DEM.13")
    if not isinstance(size, (int, float)) or not isinstance(growth, (int, float)):
        return _unknown(name, mx)
    down = down if isinstance(down, (int, float)) else 0.0
    bn = size / 1e9
    if size >= 1e9 and growth >= 0.10 and down >= 0.08:
        pts = 21 + min(4, (growth - 0.10) * 40)      # 21-25: billions, double digit
    elif size >= 2.5e8 and growth >= 0.05:
        pts = 15 + min(5, (growth - 0.05) * 100)     # 15-20: real and growing
    elif size > 0:
        pts = 8 + min(6, growth * 60)                # 8-14: small or flat
    else:
        pts = 3
    return DimensionScore(name, clamp(pts, 0, mx), mx,
                          f"Sector market EUR {bn:.0f}bn, growing {growth:.0%}, "
                          f"downstream {down:.0%} (sector level, not category)")


def _fit(rec: CompanyRecord) -> DimensionScore:
    name, mx = "Product and segment fit", 20
    present = resolved_value(rec, "DEM.05")
    price, adapt = resolved_value(rec, "DEM.06"), resolved_value(rec, "DEM.07")
    if present is None:
        return _unknown(name, mx)
    if present is False:
        return DimensionScore(name, 4.0, mx, "buying segment not present in India at scale")
    if price == "strong" and adapt == "minimal":
        pts = 18.0
    elif price in ("strong", "moderate") and adapt in ("minimal", "moderate"):
        pts = 12.0   # 12-16 anchor: segment exists, a variant or price tier is needed
    else:
        pts = 8.0
    return DimensionScore(name, pts, mx,
                          f"Segment present; price-point fit {price}, adaptation {adapt}")


def _competition(rec: CompanyRecord) -> DimensionScore:
    name, mx = "Competitive position", 15
    peers, entrants = resolved_value(rec, "DEM.11"), resolved_value(rec, "DEM.14")
    if peers is None and entrants is None:
        return _unknown(name, mx)
    # 13-15 also needs the premium end to be open, which v1 data cannot show.
    if peers and entrants:
        pts, why = 11.0, "peers earn India revenue and foreign entrants succeed"
    elif peers or entrants:
        pts, why = 8.0, "peers present; category contested"
    else:
        pts, why = 4.0, "no evidence of peers earning India revenue"
    return DimensionScore(name, pts, mx, why)


def _policy(rec: CompanyRecord) -> DimensionScore:
    name, mx = "Policy and incentives", 15
    pli, fdi = resolved_value(rec, "POL.01"), resolved_value(rec, "POL.02")
    tariff = resolved_value(rec, "DEM.08")
    if pli is None and fdi is None:
        return _unknown(name, mx)
    if fdi == "approval":
        pts, why = 3.0, "approval-route FDI"
    elif pli and fdi == "automatic" and tariff == "favourable":
        pts, why = 14.0, "sector named in an incentive scheme, automatic FDI, favourable tariffs"
    elif fdi == "automatic" and (pli or tariff == "favourable"):
        pts, why = 11.0, "automatic FDI and favourable terms, not fully sector specific"
    elif fdi == "automatic":
        pts, why = 8.0, "automatic FDI, otherwise neutral"   # top of the 4-8 neutral band
    else:
        pts, why = 5.0, "neutral policy position"
    return DimensionScore(name, pts, mx, why)


def _route(rec: CompanyRecord) -> DimensionScore:
    name, mx = "Route to market", 15
    route = (resolved_value(rec, "DEM.15") or {}).get("route")
    months = (resolved_value(rec, "DEM.16") or {}).get("approval_lead_months")
    own_presence = resolved_value(rec, "GATE.01") is True  # their own India footprint
    if route is None and not own_presence:
        return _unknown(name, mx)
    short = isinstance(months, int) and months <= 6
    if own_presence and short:
        pts, why = 13.0, "own India presence and short approval lead time"
    elif own_presence or (route == "established" and short):
        pts, why = 10.0, ("own India presence" if own_presence
                          else "established sector distribution, short approvals; no own presence")
    elif route in ("established", "partial"):
        pts, why = 9.0, f"{route} sector distribution, no own presence"   # 9-12: partial presence
    else:
        pts, why = 3.0, "no feasible route identified"
    return DimensionScore(name, pts, mx, why)


def _supply_chain(rec: CompanyRecord) -> DimensionScore:
    name, mx = "Supply chain and China plus one", 10
    c1 = resolved_value(rec, "POL.07")
    if c1 is None:
        return _unknown(name, mx)
    # 8-10 needs NAMED customers or suppliers relocating — company-specific
    # evidence the engine does not yet collect, so sector flow caps at 7.
    pts = {"strong": 6.0, "relevant": 5.0, "weak": 2.0}.get(str(c1), 1.0)  # 5-7: sector-level relocation flow
    if c1 == "n/a":
        return DimensionScore(name, pts, mx, "Not applicable to this sector")
    return DimensionScore(name, pts, mx, f"Sector relocation flow: {c1}; no named accounts")


def score_india_market(rec: CompanyRecord, settings) -> ScoreResult:
    dims = [_demand(rec), _fit(rec), _competition(rec), _policy(rec),
            _route(rec), _supply_chain(rec)]
    total = clamp(sum(d.points for d in dims), 0, 100)
    cov, resolved, applicable = coverage_for(rec, "india_market")
    conf = confidence_for(rec, "india_market", cov)
    return ScoreResult(
        key="india_market", label="India Market Opportunity", points=total,
        band=band_for(total), coverage=cov, confidence=conf, dimensions=dims,
        applicable_signals=applicable, resolved_signals=resolved,
    )
