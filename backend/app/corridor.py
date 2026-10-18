"""Which way a company is looking: the two public engines share one codebase.

EU_TO_IN is the India Market Assessment (a European company looking at
India). IN_TO_EU is the Europe Market Assessment (an Indian company looking
at Europe and the UK). Each corridor carries its own reference data, copy
and target markets; the pipeline, scrapers, verification and reports are
shared.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Corridor(str, Enum):
    EU_TO_IN = "eu_to_in"
    IN_TO_EU = "in_to_eu"


@dataclass(frozen=True)
class CorridorConfig:
    key: Corridor
    engine_name: str
    question: str
    home_region: str            # where the assessed company is based
    target_region: str          # where it wants to sell
    target_markets: tuple = field(default_factory=tuple)   # ISO-2, ranked candidates
    public_path: str = ""


CORRIDORS = {
    Corridor.EU_TO_IN: CorridorConfig(
        key=Corridor.EU_TO_IN,
        engine_name="India Market Assessment",
        question="Is India a market for what you sell, and are you ready to win it?",
        home_region="Europe", target_region="India", target_markets=("IN",),
        public_path="/engines/india-market-assessment/",
    ),
    Corridor.IN_TO_EU: CorridorConfig(
        key=Corridor.IN_TO_EU,
        engine_name="Europe Market Assessment",
        question="Is Europe a market for what you sell, and are you ready to win it?",
        home_region="India", target_region="Europe and the UK",
        # Reference v1 (18 Oct 2026): nine EU markets by 2025 imports from
        # India in the four v1 sectors, plus the UK. Ireland is 11th.
        target_markets=("DE", "IT", "FR", "NL", "ES", "BE", "PL", "SE", "CZ", "UK"),
        public_path="/engines/europe-market-assessment/",
    ),
}


def config(corridor: Corridor | str) -> CorridorConfig:
    return CORRIDORS[Corridor(corridor)]
