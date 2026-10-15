"""Deterministic scoring helpers.

A model must never compute a score (Section 1.4). Every point here is produced
by code from resolved evidence. UNKNOWN contributes nothing — never a low value.
"""
from __future__ import annotations

from datetime import date, datetime

from app.data.records import CompanyRecord


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            return None


def freshness_weight(as_of: str | None, in_flight: bool = False) -> float:
    """PRESS freshness decay (Section 5.5): full weight <=12 months, half at 24,
    zero beyond 36 — unless the event is still in flight. No date => zero."""
    if in_flight:
        return 1.0
    d = _parse_date(as_of)
    if d is None:
        return 0.0  # a PRESS signal without a date scores zero, no exception
    months = (date.today() - d).days / 30.4
    if months <= 12:
        return 1.0
    if months <= 24:
        return 0.5
    if months <= 36:
        return 0.25
    return 0.0


def resolved_true(rec: CompanyRecord, signal_id: str) -> bool:
    ev = rec.get(signal_id)
    return ev is not None and ev.is_resolved and ev.value is True


def resolved_value(rec: CompanyRecord, signal_id: str):
    ev = rec.get(signal_id)
    if ev is None or not ev.is_resolved:
        return None
    return ev.value


def clamp(points: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, round(points, 2)))
