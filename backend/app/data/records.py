"""Domain types that flow through the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.data.evidence import Evidence


class GateVerdict(str, Enum):
    """India gate outcomes (Section 3.2)."""
    CONFIRMED = "CONFIRMED"              # -> DISQUALIFIED, reason X1
    CLEAR = "CLEAR"                      # ideal profile, exec bonus
    CLEAR_GREENFIELD = "CLEAR_GREENFIELD"  # qualify, exec penalty
    CAUTION = "CAUTION"                  # thin/contradictory data, manual review


class Disposition(str, Enum):
    """What an exclusion does (Section 4)."""
    DISQUALIFY = "DISQUALIFY"  # removes the record from the pipeline
    FLAG = "FLAG"              # scoring continues, human must read before outreach
    CAUTION = "CAUTION"        # halts scoring, routes to manual review


class TitleClass(str, Enum):
    TECH = "TECH"
    NON_TECH = "NON_TECH"
    AMBIGUOUS = "AMBIGUOUS"
    IT_SUPPORT = "IT_SUPPORT"  # tracked separately; does NOT count as tech


class ResponseMode(str, Enum):
    """Public surface response modes (Section 9.4)."""
    STANDARD = "STANDARD"
    EXISTING_CENTRE = "EXISTING_CENTRE"
    SUB_SCALE = "SUB_SCALE"
    ENTERPRISE = "ENTERPRISE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    EXCLUDED = "EXCLUDED"


class Band(str, Enum):
    """Output bands (Section 8.4)."""
    VERY_STRONG = "Very strong"
    STRONG = "Strong"
    MODERATE = "Moderate"
    WEAK = "Weak"


@dataclass
class ExclusionHit:
    code: str                 # e.g. "X1"
    disposition: Disposition
    rationale: str


@dataclass
class ClassifiedTitle:
    raw: str
    normalised: str
    title_class: TitleClass
    method: str               # "dictionary" | "model"
    confidence: float


@dataclass
class GateResult:
    verdict: GateVerdict
    tech_present: bool
    title_mix: dict            # counts and shares by class (justifies the verdict)
    classified_titles: list[ClassifiedTitle] = field(default_factory=list)
    reason: str = ""


@dataclass
class DimensionScore:
    name: str
    points: float
    max_points: int
    basis: str = ""           # one-line evidenced basis shown under the bar


@dataclass
class ScoreResult:
    key: str                  # "gcc_fit" | "india_market" | "technology_hub"
    label: str
    points: float
    band: Band
    coverage: float           # per-score coverage (Section 7.1)
    confidence: float
    dimensions: list[DimensionScore] = field(default_factory=list)
    applicable_signals: int = 0
    resolved_signals: int = 0


@dataclass
class CompanyRecord:
    """The object a run assembles, tier by tier."""
    input_url: str
    # Tier 0 resolution
    resolved_name: str | None = None
    registry_id: str | None = None
    jurisdiction: str | None = None
    ultimate_parent: str | None = None
    subsidiaries: list[dict] = field(default_factory=list)
    alternate_domains: list[str] = field(default_factory=list)
    sector: str | None = None
    country: str | None = None
    resolution_failed: bool = False
    resolution_provisional: bool = False  # resolved from website, no registry id
    from_seed: bool = False               # matched a verified seed entity

    # signals keyed by signal_id -> Evidence
    signals: dict[str, Evidence] = field(default_factory=dict)

    # tier outcomes
    gate: GateResult | None = None
    exclusions: list[ExclusionHit] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    news_events: list[dict] = field(default_factory=list)   # verified newsroom events (internal)
    hq_city: str | None = None                               # headquarters city (Apollo)
    # Verified annual-report figures for the banner: year, revenue, growth, margins.
    financials: dict | None = None

    # scores
    gcc_fit: ScoreResult | None = None
    india_market: ScoreResult | None = None
    technology_hub: ScoreResult | None = None
    narrative_mode: str | None = None

    provisional_gcc_fit: float | None = None
    reached_tier3: bool = False

    def add(self, ev: Evidence) -> None:
        self.signals[ev.signal_id] = ev

    def get(self, signal_id: str) -> Evidence | None:
        return self.signals.get(signal_id)

    def source_urls(self) -> list[str]:
        """Flat list of every source URL used (Section 10, mandatory output)."""
        seen: list[str] = []
        for ev in self.signals.values():
            if ev.source_url and ev.source_url not in seen:
                seen.append(ev.source_url)
        return seen
