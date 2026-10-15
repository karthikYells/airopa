"""The evidence envelope (Section 7).

Every signal value is stored as an object, never a bare value. A bare number
with no date and no source cannot be used in outreach and must not exist in
the system.

Hard rules enforced here:
  - A signal with no source_url cannot be created, EXCEPT where source_type
    is `inference`, in which case `inference_inputs` must list the inputs.
  - UNKNOWN is a first-class value, distinct from null and from zero. The
    scoring layer treats UNKNOWN as "no points", never as a low value.
  - as_of_date (when the FACT refers to) and collected_at (when we fetched it)
    are different fields and are never conflated.
  - Where sources conflict, every value is kept in `conflicting_values` and the
    result is presented as a range; one is never silently selected.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SourceType(str, Enum):
    FILING = "filing"
    PRESS = "press"
    COMPANY_SITE = "company_site"
    JOB_POSTING = "job_posting"
    PEOPLE_DATA = "people_data"
    REGISTRY = "registry"
    REVIEW_SITE = "review_site"
    REFERENCE_DATA = "reference_data"
    INFERENCE = "inference"


class SourceAuthority(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    INFERRED = "inferred"


class Method(str, Enum):
    API = "api"
    PARSER = "parser"
    DICTIONARY = "dictionary"
    MODEL = "model"
    LOOKUP = "lookup"
    HUMAN = "human"


class _Unknown:
    """Sentinel for UNKNOWN. A singleton, distinct from None and 0.

    The scoring layer tests `value is UNKNOWN` and awards no points; it never
    treats this as a low numeric value.
    """

    _instance: "_Unknown | None" = None

    def __new__(cls) -> "_Unknown":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNKNOWN"

    def __bool__(self) -> bool:  # avoid accidental truthiness tests
        return False


UNKNOWN = _Unknown()


class EvidenceError(ValueError):
    """Raised when an evidence envelope violates a storage-layer rule."""


@dataclass
class Evidence:
    signal_id: str
    value: Any  # may be UNKNOWN
    unit: str | None = None
    as_of_date: str | None = None  # ISO date the FACT refers to
    collected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source_url: str | None = None
    source_type: SourceType | None = None
    source_authority: SourceAuthority | None = None
    confidence: float = 0.0  # 0.0 - 1.0
    method: Method | None = None
    conflicting_values: list[dict] = field(default_factory=list)
    inference_inputs: list[str] = field(default_factory=list)
    notes: str | None = None

    def __post_init__(self) -> None:
        self._validate()

    @property
    def is_unknown(self) -> bool:
        return self.value is UNKNOWN

    @property
    def is_resolved(self) -> bool:
        """A signal counts toward coverage only if it resolved WITH evidence."""
        if self.is_unknown:
            return False
        if self.source_type is SourceType.INFERENCE:
            return bool(self.inference_inputs)
        return bool(self.source_url)

    def _validate(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise EvidenceError(
                f"{self.signal_id}: confidence {self.confidence} out of range"
            )
        # UNKNOWN carries no source requirement — it is an honest absence.
        if self.is_unknown:
            return
        if self.source_type is SourceType.INFERENCE:
            if not self.inference_inputs:
                raise EvidenceError(
                    f"{self.signal_id}: inference must list inference_inputs"
                )
        elif not self.source_url:
            raise EvidenceError(
                f"{self.signal_id}: a resolved value requires a source_url "
                f"(got value={self.value!r})"
            )

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "value": "UNKNOWN" if self.is_unknown else self.value,
            "unit": self.unit,
            "as_of_date": self.as_of_date,
            "collected_at": self.collected_at,
            "source_url": self.source_url,
            "source_type": self.source_type.value if self.source_type else None,
            "source_authority": (
                self.source_authority.value if self.source_authority else None
            ),
            "confidence": self.confidence,
            "method": self.method.value if self.method else None,
            "conflicting_values": self.conflicting_values,
            "inference_inputs": self.inference_inputs,
            "notes": self.notes,
        }


def unknown(signal_id: str, notes: str | None = None) -> Evidence:
    """Convenience constructor for an honest UNKNOWN (e.g. a stubbed feed)."""
    return Evidence(signal_id=signal_id, value=UNKNOWN, notes=notes)
