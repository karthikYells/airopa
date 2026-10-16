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

export interface PeerHeadline {
  with_centre?: number;
  total?: number;
  recent_24m?: number;
  aggregate_india_headcount?: number;
  cohort_definition?: string;
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
  revenue?: string | null;
  headcount?: string | null;
}

export interface Snapshot {
  mode: string;
  reason?: string;
  message?: string;
  company?: Company;
  source_count?: number;
  disclaimer?: string;
  provisional_resolution?: boolean;
  peer_headline?: PeerHeadline | null;
  india_status?: string;
  india_market?: ScoreBlock | null;
  technology_hub?: ScoreBlock | null;
  indicative_scale?: {
    first_phase_team: string;
    indicative_saving: string;
    saving_basis?: string;
    time_to_first_team_live: string;
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
