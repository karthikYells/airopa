"""Pipeline orchestration — three tiers executed in order (Section 2).

A record that fails a tier never reaches the next one. This is what makes the
engine affordable at volume: thousands pass through Tier 1 for the cost of a
handful of Tier 3 assessments.

  Tier 0  Resolve  -> entity, parent, domains, registry id (or RESOLUTION_FAILED)
  Tier 1  Screen   -> India gate + exclusions X1–X20 + scale band
  Tier 2  Triage   -> cheap signals, provisional GCC Fit, coverage, X20
  Tier 3  Assess   -> full signal set, three scores, interactions, narrative

Tier 3 is reached by every public run that passes Tier 1, and by internal runs
whose provisional GCC Fit clears the configurable threshold (Section 2).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlparse

from app.adapters import apollo as apollo_adapter
from app.adapters import registry as registry_adapter
from app.adapters import wikidata as wikidata_adapter
from app.adapters.web_scraper import ScrapeResult, scrape
from app.config import Settings
from app.data.evidence import Evidence, Method, SourceAuthority, SourceType, UNKNOWN
from app.data.records import (
    CompanyRecord, Disposition, GateVerdict,
)
from app.exclusions.rules import evaluate_exclusions, terminal_disposition
from app.fixtures.demo_companies import get_seed
from app.gate.india_gate import run_gate
from app.reference.india_reference import lookup as reference_lookup
from app.scoring.coverage import coverage_for
from app.scoring.gcc_fit import score_gcc_fit
from app.scoring.india_market import score_india_market
from app.scoring.interactions import apply_interactions
from app.scoring.technology_hub import score_technology_hub
from app.signals.collect import collect_from_seed, collect_live, country_code
from app.signals import sector_cache
from app.signals.sector import classify_sector


@dataclass
class PipelineOutcome:
    record: CompanyRecord
    stopped_at: str | None = None        # tier where the record halted
    terminal_code: str | None = None     # exclusion code that halted it
    terminal_disposition: str | None = None
    notes: list[str] = field(default_factory=list)


def _host(input_url: str) -> str:
    u = input_url if "://" in input_url else "https://" + input_url
    return urlparse(u).netloc


def run_pipeline(
    input_url: str, settings: Settings, llm=None, *, surface: str = "public",
) -> PipelineOutcome:
    rec = CompanyRecord(input_url=input_url)
    outcome = PipelineOutcome(record=rec)

    # ---------------- Tier 0: resolve ----------------
    seed = get_seed(_host(input_url)) if settings.use_seed_data else None
    gate_inputs = None
    if seed is not None:
        gate_inputs = collect_from_seed(rec, seed, llm=llm)
    else:
        sr: ScrapeResult = scrape(input_url)
        if not sr.reachable:
            rec.resolution_failed = True
            outcome.stopped_at = "Tier 0"
            outcome.notes.append("Website unreachable — cannot assess.")
            return outcome

        # India people + firmographic gaps from Apollo (best effort; None if off).
        # Runs first so its company name can steer the Wikidata search.
        ap = apollo_adapter.fetch(sr.resolved_host or _host(input_url), settings)
        if ap is not None:
            outcome.notes.append(
                f"Apollo: {ap.india_people_count} India profiles, "
                f"{len(ap.india_job_titles)} India postings, "
                + ("cached (0 credits)." if ap.from_cache else f"{ap.credits_used} credit(s) used."))
        ap_ok = ap is not None and ap.found

        # Real firmographics from Wikidata (best effort).
        wd = wikidata_adapter.resolve(sr.resolved_host or _host(input_url),
                                      name_hint=(ap.name if ap_ok and ap.name else sr.page_title_name))

        rec.resolved_name = (wd.label if wd.found else None) \
            or (ap.name if ap_ok else None) or sr.page_title_name \
            or (sr.resolved_host or "").split(".")[0].title()
        country_label = wd.country if wd.found else (ap.country if ap_ok else None)
        rec.country = country_code(country_label)
        rec.jurisdiction = country_label
        rec.alternate_domains = []
        if wd.found and wd.qid:
            rec.registry_id = f"wikidata:{wd.qid}"
        elif settings.allow_provisional_resolution:
            rec.registry_id = f"PROVISIONAL:{sr.resolved_host}"
            rec.resolution_provisional = True
            outcome.notes.append("Resolved from the public website; no registry match.")
        else:
            rec.resolution_failed = True
            outcome.stopped_at = "Tier 0"
            return outcome

        # Classify sector -> India reference lookup (makes Scores B & C resolve).
        # A model-decided sector is remembered per domain so scores are stable.
        domain = apollo_adapter.normalise_domain(sr.resolved_host or _host(input_url))
        sector_key = sector_cache.get(domain)
        if sector_key is not None:
            sector_conf, sector_method = 0.75, "model (saved)"
        else:
            sector_key, sector_conf, sector_method = classify_sector(
                sr.homepage_text,
                wikidata_industry=(wd.industry if wd.found and wd.industry else (ap.industry if ap_ok else None)),
                llm=llm, name=rec.resolved_name)
            if sector_method == "model" and sector_key:
                sector_cache.put(domain, sector_key)
        ref = reference_lookup(sector_key)
        rec.sector = ref.sector
        outcome.notes.append(f"Sector: {ref.sector} ({sector_method}, conf {sector_conf}).")
        gate_inputs = collect_live(rec, sr, wd, ref, settings, llm=llm, apollo=ap)

    # ---------------- Tier 1: screen ----------------
    rec.gate = run_gate(gate_inputs, settings)
    # Persist derived gate fields for audit/output.
    rec.add(Evidence("GATE.06", gate_inputs.india_tech_role_count,
                     source_type=SourceType.INFERENCE,
                     inference_inputs=["classified india titles"], confidence=0.6,
                     method=Method.DICTIONARY, as_of_date=date.today().isoformat()))

    hits = evaluate_exclusions(rec, settings)
    rec.exclusions = list(hits)
    for h in hits:
        if h.disposition is Disposition.FLAG and h.code not in rec.flags:
            rec.flags.append(h.code)
    terminal = terminal_disposition(hits)
    if terminal is not None:
        outcome.stopped_at = "Tier 1"
        outcome.terminal_code = terminal.code
        outcome.terminal_disposition = terminal.disposition.value
        # The engine is market-access first: India as a market for what they
        # sell matters even when a capability centre already exists. It is a
        # reference lookup, so no Tier 3 research is spent.
        if rec.sector:
            rec.india_market = score_india_market(rec, settings)
        return outcome

    # ---------------- Tier 2: triage ----------------
    rec.gcc_fit = score_gcc_fit(rec, settings)
    rec.provisional_gcc_fit = rec.gcc_fit.points
    # X20 judges overall coverage, not GCC Fit alone: the public surface rests on
    # the India Market and Technology Hub scores, whose reference signals are
    # already present by Tier 2. Only genuinely thin records (every score below
    # the floor) are halted.
    cov2 = max(coverage_for(rec, k)[0]
               for k in ("gcc_fit", "india_market", "technology_hub"))
    hits2 = evaluate_exclusions(rec, settings, tier2_coverage=cov2)
    terminal2 = terminal_disposition(hits2)
    if terminal2 is not None and terminal2.code == "X20":
        rec.exclusions.append(terminal2)
        outcome.stopped_at = "Tier 2"
        outcome.terminal_code = terminal2.code
        outcome.terminal_disposition = terminal2.disposition.value
        return outcome

    # Internal surface stops here for below-threshold records (Section 2).
    if surface == "internal" and rec.provisional_gcc_fit < settings.tier3_provisional_score_min:
        outcome.stopped_at = "Tier 2"
        outcome.notes.append(
            f"Provisional GCC Fit {rec.provisional_gcc_fit:.0f} below Tier-3 "
            f"threshold {settings.tier3_provisional_score_min}."
        )
        # B and C are reference lookups with no research cost, so the internal
        # view still shows all three scores; no Tier 3 research is spent.
        rec.india_market = score_india_market(rec, settings)
        rec.technology_hub = score_technology_hub(rec, settings)
        return outcome

    # ---------------- Tier 3: assess ----------------
    rec.reached_tier3 = True
    rec.gcc_fit = score_gcc_fit(rec, settings)
    rec.india_market = score_india_market(rec, settings)
    rec.technology_hub = score_technology_hub(rec, settings)
    apply_interactions(rec)
    return outcome
