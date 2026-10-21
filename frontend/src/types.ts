export interface SubDimension {
  name: string;
  level: string; // word level only, never points (Section 9.2)
}

export interface ScoreBlock {
  label: string;
  question?: string;
  score: number;
  band: string;
  coverage: number;
  sub_dimensions: SubDimension[];
}

/** India as a market for what they sell: score and six dimensions in words,
 *  labelled indicative and sector-level (raw figures stay in the engine). */
export interface Market {
  label: string;
  question: string;
  score: number;
  band: string;
  coverage: number;
  headline: string;
  why: string; // one line: what lifts the score and what holds it back
  dimensions: { name: string; level: string; insight: string }[];
  basis: string;
}

/** Technology Hub Readiness: score, why line and a reason per dimension,
 *  labelled indicative (points stay in the engine). */
export interface HubCard {
  label: string;
  question: string;
  score: number;
  band: string;
  coverage: number;
  why: string;
  dimensions: { name: string; level: string; reason: string }[];
  basis: string;
}

export interface PeerHeadline {
  with_centre?: number;
  total?: number;
  recent_24m?: number;
  aggregate_india_headcount?: number;
  cohort_definition?: string;
  claim?: string;          // what the count means, worded by the engine
  aggregate_note?: string | null;
}

export interface OwnEvidence {
  title: string;
  tone?: "blue" | "orange" | "red";
  bullets: string[]; // **bold** marks emphasis
  as_of?: string;
}

export interface Company {
  input: string;
  name?: string;
  sector?: string;
  country?: string;
  location?: string | null;
  revenue?: string | null;
  headcount?: string | null;
  founded?: string | null;
  // Company-level facts from their own annual report (revenue trend, margin).
  signals?: { text: string; tone: "green" | "red" | "neutral" }[];
  signals_source?: string | null;
}

/** A Europe check in progress: what is known so far. */
export interface EuropeProgress {
  stage: "company" | "products";
  company?: Company;
  products?: { name: string; demand: string | null }[];
  products_source?: "site" | "visitor";
  segment?: string | null;
}

export interface Snapshot {
  run_id?: string;
  snapshot_token?: string; // signed copy, so the report works after an engine restart
  mode: string;
  reason?: string;
  message?: string;
  company?: Company;
  source_count?: number;
  disclaimer?: string;
  provisional_resolution?: boolean;
  peer_headline?: PeerHeadline | null;
  india_status?: string;
  // Europe Market Assessment
  engine?: string;
  europe_status?: string | null;
  readiness?: HubCard | null;
  countries?: { code: string; name: string; why: string }[];
  uk_note?: string | null;
  time_to_first_order?: { range: string; basis: string; note: string } | null;
  products_named?: string[];          // what we matched, to prefill a correction
  products_source?: "site" | "visitor";
  // The short version: a sharp summary built only from facts on the page.
  summary?: { headline: string; body: string; close: string } | null;
  market?: Market | null;
  technology_hub?: HubCard | null;
  indicative_scale?: {
    first_phase_team: string;
    team_basis?: string;
    indicative_saving: string;
    saving_basis?: string;
    time_to_first_team_live: string;
    time_basis?: string;
    note: string;
  };
  own_evidence?: OwnEvidence[];
  withheld?: string[];
  lead_capture?: { type: string; field: string; title?: string; offer?: string; sla?: string } | null;
  verified_count?: number;
  ask?: string[];
  content?: { headline: string; body: string };
}

export interface InternalScore {
  key: string;
  label: string;
  score: number;
  band: string;
  coverage_pct: number;
  confidence: number;
  resolved_signals: number;
  applicable_signals: number;
  dimensions: { name: string; points: number; max: number; basis: string }[];
}

export interface InternalBrief {
  config_version: string;
  run_at: string;
  input: string;
  entity: {
    resolved_name?: string;
    registry_id?: string;
    jurisdiction?: string;
    country?: string;
    sector?: string;
    ultimate_parent?: string;
    resolution_provisional?: boolean;
    revenue_eur?: number | null;
    headcount?: number | null;
    founded?: number | null;
    india_profiles?: number | null;
  };
  gate: {
    verdict: string;
    reason: string;
    tech_present: boolean;
    title_mix: { total: number; counts: Record<string, number>; shares: Record<string, number> };
    titles: { raw: string; class: string; method: string }[];
    evidence_note?: string | null;
  } | null;
  scores: {
    gcc_fit: InternalScore | null;
    india_market: InternalScore | null;
    technology_hub: InternalScore | null;
  };
  narrative_mode: string | null;
  flags: string[];
  exclusions: { code: string; disposition: string; rationale: string }[];
  pipeline: {
    stopped_at?: string | null;
    terminal_code?: string | null;
    reached_tier3?: boolean;
    provisional_gcc_fit?: number | null;
    notes: string[];
  };
  recommended_model: { model: string; rationale: string } | null;
  source_urls: string[];
}
