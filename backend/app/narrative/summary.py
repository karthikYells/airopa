"""The short version: a provoking summary under the company banner.

Built only from facts already on the page, in a fixed order: their peers,
their own financial pressure, India's market, their hiring, their own India
position, then what waiting costs. Each sentence needs its signal; nothing is
written where the fact is missing. No third party is named or criticised
(Section 9.1); figures stay as ranges.
"""
from __future__ import annotations

from app.data.records import CompanyRecord, GateVerdict
from app.narrative.reasoning import pct_range
from app.scoring.common import resolved_value


def build_summary(rec: CompanyRecord, peer: dict | None) -> dict | None:
    gate = rec.gate.verdict if rec.gate is not None else None
    greenfield = gate is GateVerdict.CLEAR_GREENFIELD
    entity_no_tech = gate is GateVerdict.CLEAR
    has_centre = gate is GateVerdict.CONFIRMED
    peers_ahead = bool(peer and peer.get("total") and peer["with_centre"] / peer["total"] >= 0.5)

    # Headline: the gap between them and their peers, or them and the market.
    if peers_ahead and greenfield:
        headline = "Most of your closest peers already build in India. You do not, yet."
    elif peers_ahead and entity_no_tech:
        headline = "Your peers build technology in India. You have an entity there, but no team."
    elif has_centre:
        headline = "You are already in India. The question is whether you are there at your peers' scale."
    elif peer and peer.get("with_centre"):
        headline = "Some of your closest peers are already building in India. The window is open now."
    else:
        headline = "India is moving in your sector. You are not there yet."
    if has_centre and not peer:
        headline = "You are already in India. The question is whether you are using it fully."

    body = []
    if peer and peer.get("total"):
        body.append(f"{peer['with_centre']} of your {peer['total']} closest European peers already have "
                    "technology teams in India.")
    fin = rec.financials or {}
    m_now, m_prev, g = fin.get("op_margin"), fin.get("op_margin_prev"), fin.get("revenue_growth")
    if isinstance(m_now, (int, float)) and isinstance(m_prev, (int, float)) and m_now < m_prev:
        body.append(f"Your own operating margin fell from {m_prev:.1%} to {m_now:.1%} in FY{fin['year']}"
                    + (f", on revenue {'down' if g < 0 else 'up'} {abs(g):.1%}." if isinstance(g, (int, float)) else "."))
    elif isinstance(g, (int, float)) and g < 0:
        body.append(f"Your revenue fell {abs(g):.1%} in FY{fin['year']}.")
    growth = resolved_value(rec, "DEM.03")
    if isinstance(growth, (int, float)) and growth >= 0.05 and rec.india_market and rec.india_market.points >= 60:
        body.append(f"India's market for {(rec.sector or 'your sector').lower()} is growing roughly "
                    f"{pct_range(growth)} a year.")
    open_days = resolved_value(rec, "HIRE.06")
    if isinstance(open_days, (int, float)) and open_days >= 90:
        body.append(f"Half the roles on your careers site have been open at least {int(open_days)} days.")
    if greenfield:
        body.append("You have no presence there today.")
    elif entity_no_tech:
        body.append("You already have an India entity, so the slowest part of setting up is done.")

    if len(body) < 2:
        return None   # too little to say anything sharp; better silent than generic
    if peers_ahead:
        close = "Every year you wait, their cost and capability lead compounds."
    elif has_centre:
        close = "The full business case shows how far your centre could go."
    else:
        close = "The companies that move first set the terms for those that follow."
    return {"headline": headline, "body": " ".join(body), "close": close}
