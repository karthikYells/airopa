"""Coverage and confidence (Section 7.1).

Coverage is computed per score, not once for the record, because the three
scores draw on different signal sets and can have very different evidence
quality. A score of 78 from four resolved signals is not the same object as a
78 from thirty, and the output must make that visible.
"""
from __future__ import annotations

from statistics import mean

from app.data.evidence import SourceAuthority
from app.data.records import CompanyRecord
from app.scoring.registry import SIGNALS_BY_SCORE

_AUTHORITY_WEIGHT = {
    SourceAuthority.PRIMARY: 1.0,
    SourceAuthority.SECONDARY: 0.7,
    SourceAuthority.INFERRED: 0.4,
}


def _resolved_ids(rec: CompanyRecord, signal_ids: list[str]) -> list[str]:
    out = []
    for sid in signal_ids:
        ev = rec.get(sid)
        if ev is not None and ev.is_resolved:
            out.append(sid)
    return out


def coverage_for(rec: CompanyRecord, score_key: str) -> tuple[float, int, int]:
    """Returns (coverage, resolved_count, applicable_count)."""
    applicable = SIGNALS_BY_SCORE[score_key]
    resolved = _resolved_ids(rec, applicable)
    n = len(applicable) or 1
    return round(len(resolved) / n, 4), len(resolved), len(applicable)


def confidence_for(rec: CompanyRecord, score_key: str, coverage: float) -> float:
    """f(coverage, mean source authority, conflict count, staleness).

    A transparent combination: coverage sets the ceiling, mean source authority
    and the presence of conflicts pull it down.
    """
    applicable = SIGNALS_BY_SCORE[score_key]
    resolved = [rec.get(sid) for sid in _resolved_ids(rec, applicable)]
    if not resolved:
        return 0.0
    authority = mean(
        _AUTHORITY_WEIGHT.get(ev.source_authority, 0.5) for ev in resolved
    )
    conflict_count = sum(1 for ev in resolved if ev.conflicting_values)
    conflict_penalty = min(0.2, 0.05 * conflict_count)
    return round(max(0.0, coverage * authority - conflict_penalty), 4)
