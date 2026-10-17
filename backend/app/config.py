"""Central configuration.

Every TUNE threshold from the spec lives here, loaded from the environment,
never hard-coded in logic (Design Principle, Section 3.2). Each run stores the
`config_version` so a historical score can be reproduced exactly (Section 7).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- AI model ---
    anthropic_api_key: str = ""
    llm_model_small: str = "claude-haiku-5-5"
    llm_model_large: str = "claude-sonnet-5-5"

    # --- Apollo (India people + firmographics) ---
    apollo_api_key: str = ""
    # Enrich + job postings cost 1 credit each per company; people search is free.
    # Off by default: the free India people search is what the gate needs.
    apollo_paid_calls: bool = False
    apollo_cache_days: int = 30
    # Profiles Apollo must hold for a company before "0 in India" counts as
    # evidence of no India presence (TUNE).
    apollo_min_profiles: int = 50
    # India-located profiles needed before Apollo alone counts as an India entity
    # (GATE.01). Below this, a few people are more likely remote staff or agents
    # than a legal entity (TUNE).
    apollo_india_entity_min: int = 10

    # --- storage ---
    database_url: str = "sqlite:///./data/airopa.db"

    # --- internal auth ---
    internal_api_token: str = ""

    # --- provenance ---
    config_version: str = "v3.0-build1"

    # --- v1 behaviour ---
    # When a real registry integration is absent, allow the engine to proceed on
    # a clearly-labelled PROVISIONAL resolution derived from the company's own
    # website (never a fabricated registry id). Set False once real registries
    # are wired, to restore strict Section 2.1 behaviour (no id => not scored).
    allow_provisional_resolution: bool = True
    # The seeded verified-entity store (Section 6.1) stands in for Airopa's
    # licensed registry + people + reference data until those feeds are licensed.
    use_seed_data: bool = True

    # India Market + Technology Hub (and the indicative-scale ranges) rest on the
    # v1 India reference table, which is not yet a licensed, sourced dataset
    # (Section 12 item 4). Until Airopa approves a source they are computed and
    # shown internally, but never published on the public page.
    publish_reference_scores: bool = False

    # --- public surface: abuse controls and caching (Section 9.7) ---
    public_score_limit_per_hour: int = 10    # snapshots per IP per hour
    report_limit_per_hour: int = 5           # report emails per IP per hour
    snapshot_cache_hours: float = 24         # reuse a company's snapshot this long

    # --- report email (Section 9.5) ---
    # mail_provider: "none" (queue the PDF for a person to send), "smtp" or "resend".
    mail_provider: str = "none"
    mail_from: str = "Access India Netherlands <connect@airopa.co>"
    mail_notify: str = "connect@airopa.co"   # gets a copy of every request
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    resend_api_key: str = ""
    public_site_url: str = "https://accessindia.nl/engines/india-snapshot/"
    cors_origins: str = "*"   # production: https://accessindia.nl
    # The internal view (GCC Fit) has no password by Airopa decision, so it is
    # switched off on the public deployment and used locally only.
    enable_internal: bool = True

    # --- geography (X14) ---
    target_geography: str = "NL,BE,DE,UK,Nordics,FR"

    # --- India gate TUNE thresholds (Section 3.2 / 3.3) ---
    gate_tech_role_count_min: int = 5
    gate_tech_role_share_min: float = 0.20
    gate_tech_role_share_headcount_min: int = 10
    gate_min_evidence_records: int = 10
    gate_min_evidence_records_live: int = 4  # live crawl path (fewer, targeted sources)
    gate_it_support_escalate: int = 15
    gate_ambiguous_share_caution: float = 0.40
    gate_ambiguous_min_titles: int = 10  # ambiguous-share rule needs this many titles

    # --- exclusion TUNE thresholds (Section 4.1) ---
    x5_revenue_floor_eur: int = 200_000_000
    x6_revenue_ceiling_eur: int = 5_000_000_000
    x7_headcount_floor: int = 500
    x16_min_company_age_years: int = 5
    x20_coverage_floor: float = 0.40

    # --- tier routing (Section 2) ---
    tier3_provisional_score_min: int = 55

    # --- publication safety (Section 9.6) ---
    publication_score_coverage_floor: float = 0.55
    publication_overall_coverage_floor: float = 0.40
    publication_claim_confidence_floor: float = 0.50

    @property
    def target_geography_set(self) -> set[str]:
        return {g.strip() for g in self.target_geography.split(",") if g.strip()}

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def apollo_enabled(self) -> bool:
        return bool(self.apollo_api_key)

    def snapshot(self) -> dict:
        """Thresholds actually used on a run, stored with the record (Section 7)."""
        return {
            "config_version": self.config_version,
            "gate_tech_role_count_min": self.gate_tech_role_count_min,
            "gate_tech_role_share_min": self.gate_tech_role_share_min,
            "gate_tech_role_share_headcount_min": self.gate_tech_role_share_headcount_min,
            "gate_min_evidence_records": self.gate_min_evidence_records,
            "gate_it_support_escalate": self.gate_it_support_escalate,
            "gate_ambiguous_share_caution": self.gate_ambiguous_share_caution,
            "gate_ambiguous_min_titles": self.gate_ambiguous_min_titles,
            "x5_revenue_floor_eur": self.x5_revenue_floor_eur,
            "x6_revenue_ceiling_eur": self.x6_revenue_ceiling_eur,
            "x7_headcount_floor": self.x7_headcount_floor,
            "x16_min_company_age_years": self.x16_min_company_age_years,
            "x20_coverage_floor": self.x20_coverage_floor,
            "tier3_provisional_score_min": self.tier3_provisional_score_min,
            "publication_score_coverage_floor": self.publication_score_coverage_floor,
            "publication_overall_coverage_floor": self.publication_overall_coverage_floor,
            "publication_claim_confidence_floor": self.publication_claim_confidence_floor,
            "target_geography": sorted(self.target_geography_set),
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
