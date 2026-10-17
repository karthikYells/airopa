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

import re

from app.config import Settings, get_settings
from app.narrative.reasoning import indicative_scale, reason_for
from app.narrative.summary import build_summary
from app.data.records import (
    CompanyRecord, GateVerdict, ResponseMode, ScoreResult,
)
from app.pipeline.orchestrator import PipelineOutcome
from app.scoring.common import freshness_weight


_QUESTIONS = {
    "india_market": "Is India a market for what you sell, not only a place to build?",
    "technology_hub": "Can India supply the specific skills you cannot hire today?",
}


def _word_level(points: float, max_points: int) -> str:
    """A dimension at word level (Section 9.2) — the points never leave the engine."""
    r = points / max_points if max_points else 0
    return ("Very strong" if r >= 0.8 else "Strong" if r >= 0.65
            else "Moderate" if r >= 0.5 else "Weak")


def _ratio(d) -> float:
    return d.points / d.max_points if d.max_points else 0.0


# Short names for the one-line "why this score" summary.
_SHORT = {
    "Addressable demand": "demand", "Product and segment fit": "product fit",
    "Competitive position": "competitive position", "Policy and incentives": "policy",
    "Route to market": "route to market", "Supply chain and China plus one": "supply-chain shift",
    "Talent pool depth for their stack": "talent depth", "Cost arbitrage": "cost gap",
    "IP control and security": "IP control", "Hiring velocity": "hiring speed",
    "Sector delivery precedent": "sector precedent", "Sovereignty and data risk": "data and export risk",
    "Location and infrastructure fit": "location fit",
}


# Where the plain short name reads wrong as a lift ("lifted by data risk").
_LIFT = {"Sovereignty and data risk": "few data or export constraints",
         "Cost arbitrage": "a wide cost gap"}

# Public display names (the engine's own names describe "their" side).
_DISPLAY = {"Talent pool depth for their stack": "Talent depth for your stack"}


def _why(score: ScoreResult, shown: list) -> str:
    """One sentence on what drives the score and what holds it back, from the
    dimension ratios. Words only; the points stay in the engine."""
    ranked = sorted(shown, key=_ratio, reverse=True)
    lifts = [_LIFT.get(d.name) or _SHORT.get(d.name, d.name.lower())
             for d in ranked if _ratio(d) >= 0.75][:2]
    holds = [_SHORT.get(d.name, d.name.lower()) for d in reversed(ranked) if _ratio(d) < 0.6][:2]
    out = f"{round(score.points)} out of 100"
    if lifts:
        out += ", lifted by " + " and ".join(lifts)
    if holds:
        out += ", held back by " + " and ".join(holds)
    return out + "."


def _level_idx(level: str) -> int:
    return 0 if level in ("Very strong", "Strong") else 1 if level == "Moderate" else 2


# Technology Hub reasons, by dimension and strength (strong / moderate / weak).
_TECH_REASON = {
    "Talent pool depth for their stack": (
        "India has a deep talent pool for your sector{stack}.",
        "Talent for your sector is available in India, in smaller pools{stack}.",
        "Thin India talent for your specific skills{stack}."),
    "Cost arbitrage": (
        "Comparable roles cost substantially less in India, fully loaded.",
        "A meaningful cost gap on comparable roles.",
        "A limited cost gap for your role mix."),
    "IP control and security": (
        "An owned team would give you more control over your IP than outsourced work does.",
        "Your sector is IP-intensive; how much is exposed today is for the full assessment.",
        "Your sector is IP-intensive; how much is exposed today is for the full assessment."),
    "Hiring velocity": (
        "Roles in your sector fill much faster in India than at home.",
        "Roles in your sector fill somewhat faster in India.",
        "Little difference in time to hire."),
    "Sector delivery precedent": (
        "Companies in your sector already run engineering from India.",
        "Some sector precedent for delivery from India.",
        "Little sector precedent for delivery from India yet."),
    "Sovereignty and data risk": (
        "No material data, export or defence constraints identified for your sector.",
        "Some data or export constraints to design around.",
        "Material data or export constraints for your sector."),
    "Location and infrastructure fit": (
        "Suitable cities exist for your sector{cities}.",
        "Workable cities exist for your sector{cities}, with trade-offs.",
        "Location options are limited for your sector."),
}


def _tech_hub_card(rec: CompanyRecord, settings: Settings) -> dict | None:
    """Block 5: Technology Hub Readiness with a reason per dimension. Labelled
    indicative and sector-level; company facts are added where we have them
    (their stack, their own vacancy durations)."""
    score = rec.technology_hub
    if not settings.publish_tech_hub or score is None:
        return None
    if score.coverage < settings.publication_score_coverage_floor:
        return None
    stack = _resolved(rec, "TAL.01")
    stack_txt = (f"; your own stack includes {', '.join(map(str, stack.value[:3]))}"
                 if stack and isinstance(stack.value, list) and stack.value else "")
    open_days = _resolved(rec, "HIRE.06")
    shown, dims = [], []
    for d in score.dimensions:
        if d.points <= 0:
            continue
        level = _word_level(d.points, d.max_points)
        m = re.search(r"Candidate cities ([^;]+)", d.basis)
        reason = _TECH_REASON.get(d.name, ("", "", ""))[_level_idx(level)].format(
            stack=stack_txt, cities=f", such as {m.group(1).strip()}" if m else "")
        reason = reason_for(rec, d) or reason
        if not reason_for(rec, d) and d.name == "Hiring velocity" and open_days and isinstance(open_days.value, (int, float)) \
                and open_days.value >= 90:
            reason = (f"Half of your listed roles have been open at least {open_days.value} days; "
                      "comparable roles fill faster in India.")
        shown.append(d)
        dims.append({"name": _DISPLAY.get(d.name, d.name), "level": level, "reason": reason})
    return {
        "label": score.label,
        "question": _QUESTIONS.get(score.key, ""),
        "score": round(score.points),
        "band": score.band.value,
        "coverage": round(score.coverage * 100),
        "why": _why(score, shown),
        "dimensions": dims,
        "basis": ("Indicative. Based on sector-level reference data for India and what "
                  "your own site shows; the full business case tests it against your roles."),
    }


# Plain-language market insight per dimension and strength. Words only: the
# figures behind them are sector-level v1 reference data and stay internal.
_INSIGHT = {
    "Addressable demand": (
        "India's market for your sector is large and growing fast, with demand rising downstream.",
        "India's market for your sector is real and growing, though not yet sized for your exact category.",
        "Little evidenced India demand for your category so far."),
    "Product and segment fit": (
        "Your kind of buyer exists in India at scale, and your offer fits with limited adaptation.",
        "The buying segment exists, but a variant or price tier is likely needed.",
        "Substantial adaptation would be needed to fit Indian buyers."),
    "Competitive position": (
        "Peers already earn revenue in India, and foreign entrants succeed in your category.",
        "Peers are present and the category is contested.",
        "A crowded field with established local players, or little evidence either way."),
    "Policy and incentives": (
        "Policy works for you: incentives cover your sector and foreign investment is automatic.",
        "Policy is broadly favourable, though not specific to your sector.",
        "Policy or tariffs make entry harder for your category."),
    "Route to market": (
        "A route to market exists, with established channels and short approval times.",
        "A workable route exists, with a partner or certification path to arrange.",
        "No clear route to market yet."),
    "Supply chain and China plus one": (
        "Your sector is part of the shift of supply chains into India.",
        "Your sector is touched by the China plus one shift.",
        "Supply-chain relocation is of limited relevance to your category."),
}

_MARKET_HEADLINE = {
    "Very strong": "India looks like a strong market for what you sell.",
    "Strong": "India looks like a real market for what you sell.",
    "Moderate": "India is a market for your sector, with conditions to work through.",
}


def _market_insights(rec: CompanyRecord, settings: Settings) -> dict | None:
    """Block 4 as a market-access view: the India Market Opportunity score and
    all six dimensions in words. Labelled indicative and sector-level. Omitted
    when coverage is below the publication floor, and when the score is Weak:
    under 50 the spec says do not make this argument at all (Sections 8.4, 8.5)."""
    score = rec.india_market
    if not settings.publish_market_insights or score is None:
        return None
    if score.coverage < settings.publication_score_coverage_floor or score.points < 50:
        return None
    dims, shown = [], []
    for d in score.dimensions:
        if d.points <= 0:
            continue  # unresolved: say nothing rather than guess
        if d.basis.startswith("Not applicable"):
            continue  # e.g. China plus one for software: hide, don't call it weak
        level = _word_level(d.points, d.max_points)
        texts = _INSIGHT.get(d.name)
        reason = reason_for(rec, d) or (texts[_level_idx(level)] if texts else "")
        shown.append(d)
        dims.append({"name": d.name, "level": level, "insight": reason.strip()})
    return {
        "label": "India Market Opportunity",
        "question": "Is India a market for what you sell, not only a place to build?",
        "score": round(score.points),
        "band": score.band.value,
        "coverage": round(score.coverage * 100),
        "headline": _MARKET_HEADLINE.get(score.band.value, ""),
        "why": _why(score, shown),
        "dimensions": dims,
        "basis": (f"Indicative. Based on sector-level reference data for "
                  f"{(rec.sector or 'your sector').lower()} in India, not on research into "
                  "your own products. The full business case tests this against what you sell."),
    }


def _route_fact(rec: CompanyRecord) -> str:
    """Their own position on the route to market, from the India gate."""
    v = rec.gate.verdict if rec.gate is not None else None
    if v in (GateVerdict.CONFIRMED, GateVerdict.CLEAR):
        return "Your existing India presence shortens this."
    if v is GateVerdict.CLEAR_GREENFIELD:
        return "You have no India presence of your own yet, so a partner or entity is the first step."
    return ""


def _eur(v: float) -> str:
    return f"EUR {v / 1e9:.1f}bn" if v >= 1e9 else f"EUR {v / 1e6:.0f}m"


def _company_facts(rec: CompanyRecord) -> dict:
    """Block 1: who we resolved them to. Only resolved, sourced facts appear.
    `signals` are company-level facts from their own annual report."""
    def val(sid):
        ev = rec.get(sid)
        return ev.value if ev is not None and ev.is_resolved else None
    rev, hc, founded = val("SCALE.01"), val("SCALE.04"), val("IDENT.08")
    rev_ev = rec.get("SCALE.01")
    from_report = rev_ev is not None and rev_ev.source_type is not None \
        and rev_ev.source_type.value == "filing"
    signals = []
    fin = rec.financials or {}
    g = fin.get("revenue_growth")
    if isinstance(g, (int, float)):
        signals.append({"text": f"Revenue {'up' if g >= 0 else 'down'} {abs(g):.1%} in FY{fin['year']}",
                        "tone": "green" if g > 0.02 else "red" if g < 0 else "neutral"})
    m_now, m_prev = fin.get("op_margin"), fin.get("op_margin_prev")
    if isinstance(m_now, (int, float)):
        if isinstance(m_prev, (int, float)):
            down = m_now < m_prev
            signals.append({"text": f"Operating margin {m_now:.1%}, {'down' if down else 'up'} "
                                    f"from {m_prev:.1%}",
                            "tone": "red" if down else "green"})
        else:
            signals.append({"text": f"Operating margin {m_now:.1%}", "tone": "neutral"})
    press2 = _resolved(rec, "PRESS.02")
    if press2 and press2.value is True:
        signals.append({"text": "Profit growing slower than revenue", "tone": "red"})
    location = ", ".join(x for x in (rec.hq_city, rec.jurisdiction or rec.country) if x) or None
    return {
        "input": rec.input_url,
        "name": rec.resolved_name,
        "sector": rec.sector,
        "country": rec.jurisdiction or rec.country,
        "location": location,
        "revenue": (_eur(rev) + (f" (FY{fin['year']})" if from_report and fin.get("year") else "")
                    if isinstance(rev, (int, float)) else None),
        "headcount": f"{hc:,} people" if isinstance(hc, int) else None,
        "founded": f"Founded {founded}" if isinstance(founded, int) else None,
        "signals": signals,
        "signals_source": "Your published annual report" if signals else None,
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


def _month_year(iso: str) -> str:
    try:
        y, m = int(iso[:4]), int(iso[5:7])
        return ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                "Nov", "Dec"][m - 1] + f" {y}"
    except (ValueError, IndexError):
        return iso


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
    # HIRE.06 is a lower bound: days since we first saw the role listed.
    hard_to_fill = open_days is not None and isinstance(open_days.value, (int, float)) \
        and open_days.value >= 90
    if hard_to_fill:
        bullets.append(f"Half of your listed roles have been open for **at least "
                       f"{open_days.value} days**.")
        as_of = open_days.as_of_date
    if bullets:
        panels.append({"title": ("You are hiring for roles you cannot fill" if hard_to_fill
                                 else "You are hiring now"),
                       "tone": "blue", "bullets": bullets, "as_of": as_of})

    # Panel 2 — dated pressure, from PRESS signals and their own estate.
    bullets, as_of = [], None
    # Generic, dated wording: their own events, never a third party's name
    # (an acquisition headline names the target; the page does not).
    for sid, text in [("PRESS.03", "A **cost programme** was announced{when}."),
                      ("PRESS.04", "A **restructuring** was announced{when}."),
                      ("PRESS.05", "An **ERP / S/4HANA programme** is under way{when}."),
                      ("PRESS.09", "An **acquisition** was announced{when}, with integration work to follow."),
                      ("PRESS.18", "A **site opening, closure or move** was announced{when}."),
                      ("PRESS.10", "A **new technology executive** was appointed in the last 12 months."),
                      ("PRESS.11", "A **new CEO, CFO or COO** was appointed{when}."),
                      ("PRESS.01", "Your latest results show **operating margin under pressure**{when}."),
                      ("PRESS.02", "**Profit is growing slower than revenue**{when}.")]:
        ev = _resolved(rec, sid)
        # Only a real, dated event that is still fresh: a checked "no" is not news.
        if (ev and ev.as_of_date and ev.value not in (False, None, 0, "", [], {})
                and freshness_weight(ev.as_of_date) > 0):
            from_news = ev.source_type is not None and ev.source_type.value == "company_site"
            from_report = ev.source_type is not None and ev.source_type.value == "filing"
            when = (f" in your newsroom ({_month_year(ev.as_of_date)})" if from_news
                    else f" in your FY{ev.as_of_date[:4]} annual report" if from_report
                    else " in the last 12 months" if sid == "PRESS.11" else "")
            bullets.append(text.format(when=when))
            as_of = max(as_of or "", ev.as_of_date)
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


# Block 8 (Section 9.8 contents), market access first. A conversion device,
# not an apology.
_WITHHELD = [
    "The size of India's market for your exact products, with sources",
    "Named Indian buyers and distributors in your category",
    "Tariff, certification and approval path for your products",
    "Which of your peers sell or build in India, by name",
    "Entry model: distributor, partner, own entity or capability centre",
    "City recommendation, weighing customers, talent and cost",
    "A costed plan against your own numbers",
    "A 100 day plan with named workstreams",
]


def _peer_headline(rec: CompanyRecord, seed_cohort: dict | None) -> dict | None:
    """Block 2: a count of THEIR named peer set — never the names (Section 9.1).
    Only from a verified peer set (the seeded examples today). A sector-wide
    penetration estimate is not their peers and is not shown; this block
    returns once the peer database (Section 6.1) exists."""
    pc = rec.peer_cohort
    if pc and pc.get("publishable") and get_settings().publish_peer_headline and pc.get("with_centre"):
        agg = pc.get("aggregate_india_profiles") or 0
        return {
            "with_centre": pc["with_centre"],
            "total": pc["known"],
            "claim": "of the companies we identify as your closest peers already have a team "
                     "in India with technology roles.",
            "aggregate_note": (f"Together they have at least {agg:,} people in India on public "
                               "professional profiles." if agg else None),
            "cohort_definition": pc["definition"],
        }
    if not seed_cohort:
        return None
    return {
        "with_centre": seed_cohort["with_centre"],
        "total": seed_cohort["total"],
        "recent_24m": seed_cohort.get("recent_24m"),
        "aggregate_india_headcount": seed_cohort.get("aggregate_india_headcount"),
        "cohort_definition": seed_cohort["definition"],
    }


def _peer_stats(rec: CompanyRecord, headline: dict | None) -> dict | None:
    """Peer counts for the summary: the headline's, or a publishable cohort
    with no peer in India yet (the card is hidden, the first-mover line is not)."""
    if headline:
        return headline
    pc = rec.peer_cohort
    if pc and pc.get("publishable") and get_settings().publish_peer_headline:
        return {"with_centre": pc["with_centre"], "total": pc["known"]}
    return None


def build_snapshot(outcome: PipelineOutcome, settings: Settings,
                   mode: ResponseMode, seed_cohort: dict | None = None) -> dict:
    rec = outcome.record
    sources = [u for u in rec.source_urls() if "airopa.internal" not in u]
    base = {
        "mode": mode.value,
        "company": _company_facts(rec),
        "source_count": len(sources),
        "disclaimer": ("This assessment was generated from public sources: company "
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
                            "public sources to publish an assessment.")
        base["ask"] = ["Latest revenue and headcount",
                       "Whether you operate any entity in India",
                       "Your primary ERP and core systems"]
        base["withheld"] = _WITHHELD
        base["lead_capture"] = {"type": "complete_the_picture", "field": "work_email",
                                "title": "Get your full India business case in two weeks",
                                "offer": ("We complete the picture with you and build the case against "
                                          "your own products, numbers and named peer group. No obligation.")}
        return base

    if mode is ResponseMode.SUB_SCALE:
        base["market"] = _market_insights(rec, settings)
        base["message"] = ("Below the scale where an owned India centre is the "
                            "right first step, but India may still be a market "
                            "for what you sell.")
        # Market access is the point of the engine, so a smaller company gets the
        # same case for the full assessment, framed around selling into India.
        base["peer_headline"] = _peer_headline(rec, None)
        base["india_status"] = _india_status_line(rec)
        base["technology_hub"] = _tech_hub_card(rec, settings)
        if settings.publish_reference_scores:
            base["indicative_scale"] = indicative_scale(rec)
        base["own_evidence"] = _own_evidence(rec)
        base["summary"] = build_summary(rec, _peer_stats(rec, base["peer_headline"]))
        base["withheld"] = _WITHHELD
        base["lead_capture"] = {
            "type": "sector_briefing",
            "field": "work_email",
            "title": "Get your full India market case in two weeks",
            "offer": ("Whether India is worth entering for what you sell: we build it "
                      "against your own products, your numbers and your named peer "
                      "group. No obligation, and it is yours whether or not you work "
                      "with us."),
        }
        return base


    # STANDARD and EXISTING_CENTRE share the nine-block body.
    base["peer_headline"] = _peer_headline(rec, seed_cohort)       # block 2
    base["india_status"] = _india_status_line(rec)                 # block 3
    base["market"] = _market_insights(rec, settings)               # block 4, market access
    base["technology_hub"] = _tech_hub_card(rec, settings)  # block 5
    if settings.publish_reference_scores:                          # block 6, ranges only
        base["indicative_scale"] = indicative_scale(rec)
    base["own_evidence"] = _own_evidence(rec)                      # block 7
    base["summary"] = build_summary(rec, _peer_stats(rec, base["peer_headline"]))  # under block 1
    base["withheld"] = _WITHHELD                                   # block 8
    base["lead_capture"] = {                                       # block 9
        "type": "business_case",
        "field": "work_email",
        "title": "Get your full India business case in two weeks",
        "offer": ("Selling into India, building there, or both: we build it against "
                  "your own products, your numbers and your named peer group. No "
                  "obligation, and it is yours whether or not you work with us."),
    }

    if mode is ResponseMode.ENTERPRISE:
        base["message"] = ("At your scale this deserves a direct conversation rather than a "
                           "form: the full business case is built with your team.")
        base["lead_capture"].update({"type": "route_to_partner", "sla": "one working day"})

    if mode is ResponseMode.EXISTING_CENTRE:
        # Benchmark framing: never 'disqualified', never 'nothing to gain'.
        base["message"] = ("You already have a technology presence in India. The full "
                           "picture shows how your centre compares with your peers, and "
                           "how far India could go as a market for what you sell.")
        base["lead_capture"]["offer"] = (
            "A review of your India centre against your peers, and of India as a "
            "market for your products, built by Airopa in two weeks, at no obligation.")
    return base
