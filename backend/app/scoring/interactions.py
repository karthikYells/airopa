"""How the three scores interact (Section 8.5).

The scores are independent in computation and linked in interpretation.
These three rules are implemented explicitly.
"""
from __future__ import annotations

from app.data.records import CompanyRecord
from app.scoring.bands import band_for


def apply_interactions(rec: CompanyRecord) -> None:
    """Mutates the record's GCC Fit, flags and narrative_mode in place."""
    gcc = rec.gcc_fit
    market = rec.india_market
    hub = rec.technology_hub
    if gcc is None or market is None or hub is None:
        return

    # Rule 1. Delivery gate — you cannot sell what you cannot staff.
    if hub.points < 50:
        if gcc.points > 60:
            gcc.points = 60.0
            gcc.band = band_for(gcc.points)
        if "DELIVERY_CASE_WEAK" not in rec.flags:
            rec.flags.append("DELIVERY_CASE_WEAK")

    # Rule 2. Narrative mode — decides which case the brief leads with.
    if market.points >= 65:
        rec.narrative_mode = "DUAL"       # cost and capacity, plus market access
    elif market.points >= 45:
        rec.narrative_mode = "COST_LED"   # market access as a secondary note
    else:
        rec.narrative_mode = "COST_ONLY"  # make no market-access claim


def ranking_key(rec: CompanyRecord) -> tuple[float, float]:
    """Rule 3. Rank on GCC Fit, within cohort only. Technology Hub is the
    tie-breaker, never India Market, because delivery feasibility outranks
    commercial upside. Higher sorts first."""
    gcc = rec.gcc_fit.points if rec.gcc_fit else 0.0
    hub = rec.technology_hub.points if rec.technology_hub else 0.0
    return (gcc, hub)
