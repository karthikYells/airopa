"""The internal assessment output (Section 10).

Unlike the public snapshot, this names people, peers and vendors, and shows the
GCC Fit score, its sub-scores, coverage, exclusion/flag codes and the source
list. Every panel is generated only if its supporting signals resolved
(Section 10.1) — nothing is filled with plausible text.
"""
from __future__ import annotations

from datetime import datetime

from app.config import Settings
from app.data.records import CompanyRecord, ScoreResult
from app.pipeline.orchestrator import PipelineOutcome


def _score_block(score: ScoreResult | None) -> dict | None:
    if score is None:
        return None
    return {
        "key": score.key,
        "label": score.label,
        "score": round(score.points),
        "band": score.band.value,
        "coverage_pct": round(score.coverage * 100),
        "confidence": round(score.confidence, 2),
        "resolved_signals": score.resolved_signals,
        "applicable_signals": score.applicable_signals,
        "dimensions": [
            {"name": d.name, "points": round(d.points, 1), "max": d.max_points,
             "basis": d.basis}
            for d in score.dimensions
        ],
    }


def _recommended_model(rec: CompanyRecord) -> dict:
    """Lookup from the executability profile (Section 10.4), not a judgement."""
    exec4 = rec.get("EXEC.04")
    profile = exec4.value if (exec4 and exec4.is_resolved) else None
    if profile in ("PE controlled", "PE", "owner managed"):
        model = "Build Operate Transfer (or Build Operate Transform Transfer)"
        why = "Can fund capex and has an ownership relevant event."
    elif profile in ("family", "partner owned"):
        model = "GCC as a Service on employer of record (default)"
        why = "Family or partner owned, needs proof before ownership."
    else:
        model = "Company Owned Partner Operated"
        why = "Wants the entity but not the operating burden."
    return {"model": model, "rationale": why}


def build_brief(outcome: PipelineOutcome, settings: Settings) -> dict:
    rec = outcome.record
    gate = rec.gate

    def val(sid):
        ev = rec.get(sid)
        return ev.value if ev is not None and ev.is_resolved else None

    titles = gate.classified_titles if gate is not None else []
    brief: dict = {
        "surface": "internal",
        "config_version": settings.config_version,
        "run_at": datetime.now().strftime("%d %b %Y, %H:%M"),
        "input": rec.input_url,
        "entity": {
            "resolved_name": rec.resolved_name,
            "registry_id": rec.registry_id,
            "jurisdiction": rec.jurisdiction,
            "country": rec.country,
            "sector": rec.sector,
            "ultimate_parent": rec.ultimate_parent,
            "resolution_provisional": rec.resolution_provisional,
            "from_seed": rec.from_seed,
            "revenue_eur": val("SCALE.01"),
            "headcount": val("SCALE.04"),
            "founded": val("IDENT.08"),
            "india_profiles": val("GATE.04"),
        },
        "gate": None if gate is None else {
            "verdict": gate.verdict.value,
            "reason": gate.reason,
            "tech_present": gate.tech_present,
            "title_mix": gate.title_mix,
            # The classified India titles behind the verdict (Section 3.3 audit).
            "titles": [{"raw": c.raw, "class": c.title_class.value, "method": c.method}
                       for c in titles[:120]],
            "evidence_note": (rec.get("GATE.01").notes
                              if rec.get("GATE.01") is not None else None),
        },
        "scores": {
            "gcc_fit": _score_block(rec.gcc_fit),
            "india_market": _score_block(rec.india_market),
            "technology_hub": _score_block(rec.technology_hub),
        },
        "narrative_mode": rec.narrative_mode,
        "flags": rec.flags,
        "exclusions": [
            {"code": h.code, "disposition": h.disposition.value,
             "rationale": h.rationale}
            for h in rec.exclusions
        ],
        "pipeline": {
            "stopped_at": outcome.stopped_at,
            "terminal_code": outcome.terminal_code,
            "terminal_disposition": outcome.terminal_disposition,
            "reached_tier3": rec.reached_tier3,
            "provisional_gcc_fit": rec.provisional_gcc_fit,
            "notes": outcome.notes,
        },
        "recommended_model": _recommended_model(rec) if rec.reached_tier3 else None,
        "source_urls": rec.source_urls(),
        # Verified newsroom events (headline, date, URL, type). Internal only.
        "news_events": rec.news_events,
        # Peer set with names and verified India status (Section 5.8). Internal only.
        "peer_cohort": rec.peer_cohort,
        "signals": {sid: ev.to_dict() for sid, ev in sorted(rec.signals.items())},
    }
    return brief
