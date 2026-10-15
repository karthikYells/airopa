"""Output bands (Section 8.4). The same labels apply to all three scores."""
from __future__ import annotations

from app.data.records import Band


def band_for(points: float) -> Band:
    if points >= 80:
        return Band.VERY_STRONG
    if points >= 65:
        return Band.STRONG
    if points >= 50:
        return Band.MODERATE
    return Band.WEAK
