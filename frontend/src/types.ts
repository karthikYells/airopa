export interface ScoreBlock {
  label: string;
  score: number;
  band: string;
  coverage: number;
  sub_dimensions: string[];
}

export interface PeerHeadline {
  with_centre?: number;
  total?: number;
  recent_24m?: number;
  aggregate_india_headcount?: number;
  cohort_definition?: string;
  penetration_pct?: number;
}

export interface OwnEvidence {
  title: string;
  detail: string;
  as_of?: string;
}

export interface Snapshot {
  mode: string;
  reason?: string;
  message?: string;
  company?: { input: string; name?: string; sector?: string; country?: string };
  disclaimer?: string;
  provisional_resolution?: boolean;
  peer_headline?: PeerHeadline | null;
  india_status?: string;
  india_market?: ScoreBlock | null;
  technology_hub?: ScoreBlock | null;
  indicative_scale?: {
    first_phase_team: string;
    indicative_saving: string;
    time_to_first_team_live: string;
    note: string;
  };
  own_evidence?: OwnEvidence[];
  withheld?: string[];
  lead_capture?: { type: string; field: string; offer?: string; sla?: string } | null;
  verified_count?: number;
  ask?: string[];
  content?: { headline: string; body: string };
}

export interface InternalBrief {
  entity: Record<string, unknown>;
  gate: { verdict: string; reason: string; tech_present: boolean; title_mix: any } | null;
  scores: {
    gcc_fit: InternalScore | null;
    india_market: InternalScore | null;
    technology_hub: InternalScore | null;
  };
  narrative_mode: string | null;
  flags: string[];
  exclusions: { code: string; disposition: string; rationale: string }[];
  pipeline: Record<string, unknown>;
  recommended_model: { model: string; rationale: string } | null;
  source_urls: string[];
}

export interface InternalScore {
  label: string;
  score: number;
  band: string;
  coverage_pct: number;
  confidence: number;
  resolved_signals: number;
  applicable_signals: number;
  dimensions: { name: string; points: number; max: number; basis: string }[];
}
