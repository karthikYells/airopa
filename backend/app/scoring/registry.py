"""Signal applicability per score, for coverage computation (Section 7.1).

coverage[S] = resolved_signals_with_evidence(S) / applicable_signals(S)

`applicable` excludes signals irrelevant to the sector (for example CAD/BIM
signals for a financial services company). v1 treats all listed signals as
applicable; the sector-aware exclusion is a documented extension point.
"""
from __future__ import annotations

# The signal IDs that feed each score. Mirrors the dimension tables in
# Sections 8.1–8.3. Used for coverage and to decide which signals to collect.
GCC_FIT_SIGNALS: list[str] = [
    # Addressable scope (35)
    "SCOPE.01", "SCOPE.02", "SCOPE.03", "SCOPE.04", "SCOPE.05", "SCOPE.06",
    "SCOPE.07", "SCOPE.08", "SCOPE.09", "SCOPE.10", "SCOPE.11", "SCOPE.12",
    "SCOPE.13", "SCOPE.14", "SCOPE.15", "SCOPE.16",
    # Dated pressure (30)
    "PRESS.01", "PRESS.02", "PRESS.03", "PRESS.04", "PRESS.05", "PRESS.06",
    "PRESS.07", "PRESS.08", "PRESS.09", "PRESS.10", "PRESS.11", "PRESS.12",
    "PRESS.13", "PRESS.14", "PRESS.15", "PRESS.16", "PRESS.17", "PRESS.18",
    # Executability (20)
    "EXEC.01", "EXEC.02", "EXEC.03", "EXEC.04", "EXEC.05", "EXEC.06",
    "EXEC.07", "EXEC.08", "EXEC.09", "EXEC.10", "EXEC.11", "EXEC.12",
    "EXEC.13", "EXEC.14", "EXEC.15",
    # Scale fit (15)
    "SCALE.01", "SCALE.02", "SCALE.03", "SCALE.04", "SCALE.05", "SCALE.06",
    "SCALE.07", "SCALE.08", "SCALE.09", "SCALE.10", "SCALE.11", "SCALE.12",
    "SCALE.13",
]

INDIA_MARKET_SIGNALS: list[str] = [
    "DEM.01", "DEM.02", "DEM.03", "DEM.04", "DEM.05", "DEM.06", "DEM.07",
    "DEM.08", "DEM.09", "DEM.10", "DEM.11", "DEM.12", "DEM.13", "DEM.14",
    "DEM.15", "DEM.16",
    "POL.01", "POL.02", "POL.03", "POL.04", "POL.05", "POL.06", "POL.07",
    "POL.08", "POL.09", "POL.10",
]

TECHNOLOGY_HUB_SIGNALS: list[str] = [
    "TAL.01", "TAL.02", "TAL.03", "TAL.04", "TAL.05", "TAL.06", "TAL.07",
    "TAL.08", "TAL.09", "TAL.10", "TAL.11", "TAL.12", "TAL.13", "TAL.14",
    "TAL.15", "TAL.16",
    "COST.01", "COST.02", "COST.03", "COST.04", "COST.05", "COST.06", "COST.07",
    "IPR.30", "IPR.31", "IPR.32", "IPR.33", "IPR.34",
    "SOV.01", "SOV.02", "SOV.03", "SOV.04", "SOV.05", "SOV.06", "SOV.07", "SOV.08",
    "PEER.13", "PEER.30",
]

SIGNALS_BY_SCORE: dict[str, list[str]] = {
    "gcc_fit": GCC_FIT_SIGNALS,
    "india_market": INDIA_MARKET_SIGNALS,
    "technology_hub": TECHNOLOGY_HUB_SIGNALS,
}
