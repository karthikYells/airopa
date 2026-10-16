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


_QUESTIONS = {
    "india_market": "Is India a market for what you sell, not only a place to build?",
    "technology_hub": "Can India supply the specific skills you cannot hire today?",
}


def _word_level(points: float, max_points: int) -> str:
    """A dimension at word level (Section 9.2) — the points never leave the engine."""
    r = points / max_points if max_points else 0
    return ("Very strong" if r >= 0.8 else "Strong" if r >= 0.65
            else "Moderate" if r >= 0.5 else "Weak")


def _published_score(score: ScoreResult, settings: Settings) -> dict | None:
    """Score block with three named sub-dimensions at WORD level, not points
    (Section 9.2). None when coverage is below the publication floor, or while
    the India reference data is not approved for publication."""
    if not settings.publish_reference_scores:
        return None
    if score is None or score.coverage < settings.publication_score_coverage_floor:
        return None
    resolved = [d for d in score.dimensions if d.points > 0]
    top = sorted(resolved, key=lambda d: d.max_points, reverse=True)[:3]
    return {
        "label": score.label,
        "question": _QUESTIONS.get(score.key, ""),
        "score": round(score.points),
        "band": score.band.value,
        "coverage": round(score.coverage * 100),
        "sub_dimensions": [{"name": d.name, "level": _word_level(d.points, d.max_points)}
                           for d in top],
    }


def _company_facts(rec: CompanyRecord) -> dict:
    """Block 1: who we resolved them to. Only resolved, sourced facts appear."""
    def val(sid):
        ev = rec.get(sid)
        return ev.value if ev is not None and ev.is_resolved else None
    rev, hc = val("SCALE.01"), val("SCALE.04")
    return {
        "input": rec.input_url,
        "name": rec.resolved_name,
        "sector": rec.sector,
        "country": rec.jurisdiction or rec.country,
        "revenue": (f"EUR {rev / 1e9:.1f}bn" if isinstance(rev, (int, float)) and rev >= 1e9
                    else f"EUR {rev / 1e6:.0f}m" if isinstance(rev, (int, float)) else None),
        "headcount": f"{hc:,} people" if isinstance(hc, int) else None,
    }


def _india_status_line(rec: CompanyRecord) -> str:
    """Stated as fact, not as a verdict (Section 9.2 block 3)."""
    if rec.gate is None:
        return "India presence could not be determined from public sources."
    v = rec.gate.verdict
    if v is GateVerdict.CONFIRMED:
        return ("You already operate an India capability centre with technology "
                "roles in place.")
    # Attributed to public sources: these two rest on people data and site
    # crawls, which can miss a small entity or count remote staff.
    if v is GateVerdict.CLEAR:
        return ("Public sources show an India presence, but no technology roles "
                "staffed there today.")
    if v is GateVerdict.CLEAR_GREENFIELD:
        return ("Public sources show no India entity and no India technology "
                "presence today.")
    return "Your India status could not be confirmed from public sources."


def _resolved(rec: CompanyRecord, sid: str):
    ev = rec.get(sid)
    return ev if ev is not None and ev.is_resolved else None


def _own_evidence(rec: CompanyRecord) -> list[dict]:
    """Block 7: up to three panels, each built ONLY from resolved facts about
    their own company, every bullet dated (Section 9.2, 10.1). A panel with no
    supporting signal is omitted, never filled with plausible text."""
    panels: list[dict] = []

    # Panel 1 — hiring. "Cannot fill" is claimed only with vacancy duration.
    bullets, as_of = [], None
    open_days = _resolved(rec, "HIRE.06")
    roles, tech_share = _resolved(rec, "HIRE.01"), _resolved(rec, "HIRE.04")
    if roles:
        line = f"**{roles.value} open roles** on your careers site today"
        if tech_share and isinstance(tech_share.value, (int, float)) and tech_share.value > 0:
            line += f", about {tech_share.value:.0%} of them technology or engineering"
        bullets.append(line + ".")
        as_of = roles.as_of_date
    if open_days:
        bullets.append(f"Roles have stayed open around **{open_days.value} days**.")
        as_of = open_days.as_of_date
    if bullets:
        panels.append({"title": ("You are hiring for roles you cannot fill" if open_days
                                 else "You are hiring now"),
                       "tone": "blue", "bullets": bullets, "as_of": as_of})

    # Panel 2 — dated pressure, from PRESS signals and their own estate.
    bullets, as_of = [], None
    for sid, text in [("PRESS.05", "An **S/4HANA migration** is in flight or ECC end of support applies."),
                      ("PRESS.10", "A **new technology executive** was appointed in the last 12 months."),
                      ("PRESS.03", "A **cost programme** with a stated target and deadline is public."),
                      ("PRESS.01", "Your latest results show **operating margin under pressure**.")]:
        ev = _resolved(rec, sid)
        if ev and ev.as_of_date:
            bullets.append(text); as_of = as_of or ev.as_of_date
    erp = _resolved(rec, "SCOPE.01")
    if erp and _resolved(rec, "PRESS.05"):
        erp = None  # the S/4HANA bullet above already covers their ERP
    if erp:
        bullets.append(f"**{erp.value}** appears on your own site as part of your estate.")
        as_of = as_of or erp.as_of_date
    if bullets:
        panels.append({"title": "Your timing is not neutral" if len(bullets) > 1 or not erp
                                else "Your technology estate",
                       "tone": "orange", "bullets": bullets, "as_of": as_of})

    # Panel 3 — IP exposure: structure only, never a name (Section 5.17.4).
    ipr = _resolved(rec, "IPR.33") or _resolved(rec, "IPR.32")
    if ipr and ipr.value is True:
        panels.append({
            "title": "Your IP is already exposed", "tone": "red",
            "bullets": ["Design or engineering work is delivered by an **external vendor** "
                        "that publicly lists companies in your sector as clients."],
            "as_of": ipr.as_of_date,
        })
    return panels


# Block 8 (Section 9.8 contents). A conversion device, not an apology.
_WITHHELD = [
    "Which peers run India centres, by name, and the size and function of each centre",
    "Your vendors by name, and exactly which of your competitors they also serve",
    "The specific roles to move first, and what must stay in Europe",
    "A costed team model against your own salary bands",
    "City recommendation and why, with attrition and salary data",
    "Ownership model: employer of record, partner operated, or build and transfer",
    "Works council sequencing and your data residency constraints",
    "A 100 day plan with named workstreams",
]


def _peer_headline(rec: CompanyRecord, seed_cohort: dict | None) -> dict | None:
    """Block 2: a count of THEIR named peer set — never the names (Section 9.1).
    Only from a verified peer set (the seeded examples today). A sector-wide
    penetration estimate is not their peers and is not shown; this block
    returns once the peer database (Section 6.1) exists."""
    if not seed_cohort:
        return None
    return {
        "with_centre": seed_cohort["with_centre"],
        "total": seed_cohort["total"],
        "recent_24m": seed_cohort.get("recent_24m"),
        "aggregate_india_headcount": seed_cohort.get("aggregate_india_headcount"),
        "cohort_definition": seed_cohort["definition"],
    }


def build_snapshot(outcome: PipelineOutcome, settings: Settings,
                   mode: ResponseMode, seed_cohort: dict | None = None) -> dict:
    rec = outcome.record
    sources = [u for u in rec.source_urls() if "airopa.internal" not in u]
    base = {
        "mode": mode.value,
        "company": _company_facts(rec),
        "source_count": len(sources),
        "disclaimer": ("This snapshot was generated from public sources: company "
                       "websites, corporate registries and people data"
                       + (f", {len(sources)} source{'s' if len(sources) != 1 else ''}. "
                          if sources else ". ")
                       + "Figures carry the date of the source they came from. Where we "
                       "could not verify something, we left it out rather than "
                       "estimating it. Ranges are indicative and are not an offer or "
                       "a quotation. Nothing here is a statement about the conduct of "
                       "any named third party."),
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
    if settings.publish_reference_scores:                          # block 6, ranges only
        base["indicative_scale"] = {
            "first_phase_team": "20 to 35 people",
            "indicative_saving": "50 to 60%",
            "saving_basis": "on the fully loaded cost of comparable roles",
            "time_to_first_team_live": "4 to 6 months",
            "note": "Ranges only. Your actual numbers depend on scope.",
        }
    base["own_evidence"] = _own_evidence(rec)                      # block 7
    base["withheld"] = _WITHHELD                                   # block 8
    base["lead_capture"] = {                                       # block 9
        "type": "business_case",
        "field": "work_email",
        "title": "Get the full business case in two weeks",
        "offer": ("We build it against your actual estate, your salary bands and "
                  "your named peer group. No obligation, and it is yours whether "
                  "or not you work with us."),
    }

    if mode is ResponseMode.EXISTING_CENTRE:
        # Benchmark framing — never 'disqualified', never 'nothing to gain'.
        base["message"] = ("Your existing India centre, benchmarked against your "
                           "peers on scale and function mix — and where the gap is.")
        base["lead_capture"]["offer"] = (
            "A scale up and transformation review of your existing India centre, "
            "built by Airopa in two weeks, at no obligation.")
    return base
