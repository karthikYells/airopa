"""The public self-serve snapshot (Section 9).

A lead-generation surface, not a complete report. The rule (Section 9.1):
show facts about their OWN company, counts/shares/ranges, that a structural
exposure exists, and the shape of the opportunity — withhold the underlying
lists, the names, any costed model, and the plan. The single strongest withhold
is the peer names.

Every block here is built so the output passes narrative.safety.assert_public_safe:
no GCC Fit, no peer/vendor/individual names, ranges not point estimates, and a
score is shown only when its own coverage clears the publication floor — below
that it is absent from the page entirely, never hedged (Section 9.6).
"""
from __future__ import annotations

from app.config import Settings
from app.data.records import (
    CompanyRecord, GateVerdict, ResponseMode, ScoreResult,
)
from app.pipeline.orchestrator import PipelineOutcome


def _published_score(score: ScoreResult, settings: Settings) -> dict | None:
    """Score block with three named sub-dimensions at WORD level, not points
    (Section 9.2). Returns None when coverage is below the publication floor."""
    if score is None or score.coverage < settings.publication_score_coverage_floor:
        return None
    top = sorted(score.dimensions, key=lambda d: d.points, reverse=True)[:3]
    return {
        "label": score.label,
        "score": round(score.points),
        "band": score.band.value,
        "coverage": round(score.coverage * 100),
        "sub_dimensions": [d.name for d in top],  # words, never points
    }


def _india_status_line(rec: CompanyRecord) -> str:
    """Stated as fact, not as a verdict (Section 9.2 block 3)."""
    if rec.gate is None:
        return "India presence could not be determined from public sources."
    v = rec.gate.verdict
    if v is GateVerdict.CONFIRMED:
        return ("You already operate an India capability centre with technology "
                "roles in place.")
    if v is GateVerdict.CLEAR:
        return ("You have an India entity, but no technology roles are staffed "
                "there today.")
    if v is GateVerdict.CLEAR_GREENFIELD:
        return "You have no India entity and no India technology presence today."
    return "Your India status could not be confirmed from public sources."


def _own_evidence(rec: CompanyRecord) -> list[dict]:
    """Three panels, each a fact about THEIR company, with a date (Section 9.2
    block 7). No third-party names appear."""
    panels: list[dict] = []
    hire = rec.get("HIRE.06") or rec.get("HIRE.01")
    if hire and hire.is_resolved:
        panels.append({
            "title": "Hiring you cannot fill",
            "detail": (f"Roles have stayed open around {hire.value} days with "
                       "repeated repostings." if "HIRE.06" in rec.signals
                       else f"{hire.value} open roles currently advertised."),
            "as_of": hire.as_of_date,
        })
    press = next((rec.get(s) for s in ["PRESS.12", "PRESS.05", "PRESS.03", "PRESS.10"]
                  if rec.get(s) and rec.get(s).is_resolved), None)
    if press:
        panels.append({
            "title": "Timing that is not neutral",
            "detail": "A dated, public event is creating pressure on delivery now.",
            "as_of": press.as_of_date,
        })
    ipr = rec.get("IPR.33") or rec.get("IPR.32")
    if ipr and ipr.is_resolved and ipr.value is True:
        panels.append({
            "title": "IP exposure",
            "detail": ("Design or engineering work is delivered by an external "
                       "vendor that also serves companies in your sector — your "
                       "IP sits inside another company's perimeter."),
            "as_of": ipr.as_of_date,
        })
    return panels


_WITHHELD = [
    "Which peers run India centres, and where",
    "The vendor whose teams also serve your competitors",
    "A costed team against your own salary bands",
    "The city recommendation and the ownership model",
    "The role by role plan for what moves and what stays",
]


def _peer_headline(rec: CompanyRecord, seed_cohort: dict | None) -> dict | None:
    """Counts and cohort definition only — never the names (Section 9.1)."""
    if seed_cohort:
        return {
            "with_centre": seed_cohort["with_centre"],
            "total": seed_cohort["total"],
            "recent_24m": seed_cohort.get("recent_24m"),
            "aggregate_india_headcount": seed_cohort.get("aggregate_india_headcount"),
            "cohort_definition": seed_cohort["definition"],
        }
    pen = rec.get("PEER.30")
    if pen and pen.is_resolved:
        recent = rec.get("PEER.32")
        definition = (f"{rec.sector} companies in {rec.country}"
                      if rec.sector and rec.country
                      else (f"{rec.sector} companies" if rec.sector
                            else "peer set by country, sub-sector and revenue band"))
        out = {"penetration_pct": round(pen.value * 100), "cohort_definition": definition}
        if recent and recent.is_resolved:
            out["recent_24m"] = recent.value
        return out
    return None


def build_snapshot(outcome: PipelineOutcome, settings: Settings,
                   mode: ResponseMode, seed_cohort: dict | None = None) -> dict:
    rec = outcome.record
    base = {
        "mode": mode.value,
        "company": {
            "input": rec.input_url,
            "name": rec.resolved_name,
            "sector": rec.sector,
            "country": rec.country,
        },
        "disclaimer": ("Indicative and compiled from public sources. Unverified "
                       "items are omitted, not estimated. Nothing here is a "
                       "statement about any third party's conduct."),
        "provisional_resolution": rec.resolution_provisional,
    }

    if mode is ResponseMode.EXCLUDED:
        base["content"] = {
            "headline": "India capability centres, in brief",
            "body": ("A general overview of how European mid market companies "
                     "build owned technology teams in India."),
        }
        base["lead_capture"] = None
        return base

    if mode is ResponseMode.INSUFFICIENT_DATA:
        verified = [sid for sid, ev in rec.signals.items() if ev.is_resolved]
        base["verified_count"] = len(verified)
        base["message"] = ("We could not verify enough about this company from "
                            "public sources to publish a snapshot.")
        base["ask"] = ["Latest revenue and headcount",
                       "Whether you operate any entity in India",
                       "Your primary ERP and core systems"]
        base["lead_capture"] = {"type": "complete_the_picture",
                                 "field": "work_email"}
        return base

    if mode is ResponseMode.SUB_SCALE:
        base["india_market"] = _published_score(rec.india_market, settings)
        base["message"] = ("Below the scale where an owned India centre is the "
                            "right first step — but India may still be a market "
                            "for what you sell.")
        base["lead_capture"] = {"type": "sector_briefing", "field": "work_email"}
        return base

    if mode is ResponseMode.ENTERPRISE:
        base["india_market"] = _published_score(rec.india_market, settings)
        base["technology_hub"] = _published_score(rec.technology_hub, settings)
        base["message"] = ("At your scale this deserves a direct conversation "
                            "rather than a form.")
        base["lead_capture"] = {"type": "route_to_partner", "field": "work_email",
                                "sla": "one working day"}
        return base

    # STANDARD and EXISTING_CENTRE share the nine-block body.
    base["peer_headline"] = _peer_headline(rec, seed_cohort)       # block 2
    base["india_status"] = _india_status_line(rec)                 # block 3
    base["india_market"] = _published_score(rec.india_market, settings)      # block 4
    base["technology_hub"] = _published_score(rec.technology_hub, settings)  # block 5
    base["indicative_scale"] = {                                   # block 6, ranges only
        "first_phase_team": "20 to 35 FTE",
        "indicative_saving": "50 to 60 percent on the addressable cost base",
        "time_to_first_team_live": "4 to 6 months",
        "note": "Indicative ranges, not an offer.",
    }
    base["own_evidence"] = _own_evidence(rec)                      # block 7
    base["withheld"] = _WITHHELD                                   # block 8
    base["lead_capture"] = {                                       # block 9
        "type": "business_case",
        "field": "work_email",
        "offer": ("A full business case, built by Airopa in two weeks, at no "
                  "obligation — yours whether or not you engage us."),
    }

    if mode is ResponseMode.EXISTING_CENTRE:
        # Benchmark framing — never 'disqualified', never 'nothing to gain'.
        base["message"] = ("Your existing India centre, benchmarked against your "
                           "peers on scale and function mix — and where the gap is.")
        base["lead_capture"]["offer"] = (
            "A scale up and transformation review of your existing India centre, "
            "built by Airopa in two weeks, at no obligation.")
    return base
