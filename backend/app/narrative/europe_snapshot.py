"""Public page for the Europe Market Assessment (spec v1.1 section 9).

Same rules as the India page: facts about their own company are shown;
everything else is a count, share or range; no third-party names; rules still
flagged "to verify" never appear. The shape matches the India page's blocks so
the frontend reuses its components: `market` and `readiness` cards with a
reason per dimension, `summary`, `own_evidence`, `withheld`, `lead_capture`.
"""
from __future__ import annotations

from app.narrative.public_snapshot import _eur, _word_level
from app.narrative.reasoning import eur_range, pct_range
from app.reference import europe_reference as ref

KIND = {"goods": "Goods exporter", "services": "Services", "both": "Goods and services"}

WITHHELD = [
    "Named European buyers, distributors and agents in your category",
    "Which Indian peers sell in Europe, by name, and how they entered",
    "The exact certification route, test labs and cost for your products",
    "Market size for your exact products in each country, with sources",
    "Entity and tax set-up: branch, subsidiary or partner; VAT and customs",
    "Pricing against European competitors",
    "A costed entry plan against your own numbers",
    "A 100-day plan with named workstreams",
]


_SHORT = {
    "Addressable demand": "Europe's demand", "Product and segment fit": "product fit",
    "Competitive position": "India's position", "Tariffs and trade terms": "tariffs",
    "Route to market": "route to market", "Europe's shift away from China": "the shift away from China",
    "Certification and compliance": "certifications", "Regulatory exposure handled": "EU rules",
    "Europe presence": "European presence", "European customer proof": "European customer proof",
    "Localisation and commercial readiness": "localisation", "Scale to deliver": "scale",
}


def _why(score, shown) -> str:
    r = lambda d: d.points / d.max_points if d.max_points else 0
    ranked = sorted(shown, key=r, reverse=True)
    lifts = [_SHORT.get(d.name, d.name) for d in ranked if r(d) >= 0.75][:2]
    holds = [_SHORT.get(d.name, d.name) for d in reversed(ranked) if r(d) < 0.6][:2]
    out = f"{round(score.points)} out of 100"
    if lifts:
        out += ", lifted by " + " and ".join(lifts)
    if holds:
        out += ", held back by " + " and ".join(holds)
    return out + "."


def _card(score, question: str, basis: str, key: str) -> dict:
    dims = [{"name": d.name, "level": "Not resolved" if d.basis.startswith("Not resolved") else _word_level(d.points, d.max_points),
             key: d.basis} for d in score.dimensions]
    return {"label": score.label, "question": question, "score": round(score.points),
            "band": score.band.value, "coverage": round(score.coverage * 100),
            "why": _why(score, [d for d in score.dimensions if d.points > 0]),
            "dimensions": dims, "basis": basis}


def _company(a) -> dict:
    org = a.org or {}
    fin = a.financials or {}
    rev = fin.get("revenue") or org.get("revenue_eur")
    people = org.get("employees") or (a.presence.total_people if a.presence else None)
    sector = ref.SECTORS.get(a.offering.sector) if a.offering and a.offering.sector else None
    signals = []
    g = fin.get("revenue_growth")
    if isinstance(g, (int, float)):
        signals.append({"text": f"Revenue {'up' if g >= 0 else 'down'} {abs(g):.1%} in FY{fin['year']}",
                        "tone": "green" if g > 0.02 else "red" if g < 0 else "neutral"})
    m, mp = fin.get("op_margin"), fin.get("op_margin_prev")
    if isinstance(m, (int, float)):
        if isinstance(mp, (int, float)):
            signals.append({"text": f"Operating margin {m:.1%}, {'down' if m < mp else 'up'} from {mp:.1%}",
                            "tone": "red" if m < mp else "green"})
        else:
            signals.append({"text": f"Operating margin {m:.1%}", "tone": "neutral"})
    return {
        "input": a.input_url, "name": a.name,
        "sector": " · ".join(x for x in (sector, KIND.get(a.offering.kind) if a.offering else None) if x) or None,
        "location": ", ".join(x for x in (org.get("city"), "India") if x),
        "revenue": (_eur(rev) + (f" (FY{fin['year']})" if fin.get("year") else "")) if rev else None,
        "headcount": f"{people:,} people" if people else None,
        "signals": signals,
        "signals_source": "Your published annual report" if signals else None,
    }


def _known_total(c: dict) -> int:
    """Verified competitors whose size we know (20+ people on public profiles).
    Tiny or unknown sellers are left out of the base: we cannot tell whether
    they have anyone in Europe, so counting them would understate the share."""
    listed = c.get("competitors")
    if not listed:
        return c.get("confirmed", 0)
    return sum(1 for x in listed if x.get("known") or x.get("europe_people", 0) >= 5)


def _strong(c: dict | None) -> bool:
    """The competitor story leads the page only when it is a real pattern:
    3+ verified competitors in Europe out of 5+ of known size. Market leaders
    often block automated reads, so a thin count says more about what we could
    verify than about the market, and is not headlined."""
    return bool(c) and c.get("in_europe", 0) >= 3 and _known_total(c) >= 5


def _competitor_card(a) -> dict | None:
    c = a.competitors
    if not _strong(c):
        return None
    seg = a.offering.segment if a.offering and a.offering.segment else "what you sell"
    return {"with_centre": c["in_europe"], "total": _known_total(c),
            "claim": f"companies selling {seg} already have teams in Europe.",
            "aggregate_note": (f"Together they have at least {c['europe_people']:,} people there"
                               + (f", {c['recent_people']:,} of whom started in the last 12 months." if c.get("recent_people") else ".")),
            "cohort_definition": "companies with the same offering as yours, each checked against its own website"}


def _peer(a) -> dict | None:
    pc = a.peer_cohort
    if not (pc and pc.get("publishable") and pc.get("with_presence")):
        return None
    sector = ref.SECTORS.get(a.offering.sector) if a.offering and a.offering.sector else None
    definition = pc["definition"].replace("Indian industry companies", f"Indian {(sector or 'industry').lower()} companies")
    return {"with_centre": pc["with_presence"], "total": pc["known"],
            "claim": ("of the companies we identify as your closest Indian peers already "
                      + ("has a team" if pc["with_presence"] == 1 else "have teams") + " in Europe."),
            "aggregate_note": ((f"Together they have at least {pc['europe_people']:,} people in Europe on public "
                                "professional profiles" + (f", {pc['recent_people']:,} of whom started their roles there "
                                "in the last 12 months." if pc.get("recent_people") else "."))
                               if pc.get("europe_people") else None),
            "cohort_definition": definition}


def _summary(a, peer: dict | None = None) -> dict | None:
    mk, rd = a.market.points, a.ready.points
    best = max((d for d in a.demand if d["view"]), key=lambda d: d["view"]["extra_eu"], default=None)
    if mk >= 65 and rd < 55:
        headline = "Europe is buying what you sell. You are not yet ready to win it."
    elif mk >= 65:
        headline = "Europe is buying what you sell, and you are closer to ready than most."
    elif mk >= 50:
        headline = "Europe is a real but selective market for what you sell."
    else:
        headline = "Europe is a hard market for what you sell today."
    body = []
    pc = a.peer_cohort
    if peer:
        verb = "has a team" if peer["with_centre"] == 1 else "have teams"
        body.append(f"{peer['with_centre']} of your {peer['total']} closest Indian peers already {verb} in Europe"
                    + (f", and in the last 12 months alone they put {pc['recent_people']:,} more people into "
                       "European roles: they are building their lead while you decide." if pc and pc.get("recent_people") else "."))
        if peer["with_centre"] / peer["total"] >= 0.5 and (a.presence and a.presence.verdict != "ESTABLISHED"):
            headline = "Most of your closest Indian peers are already in Europe. You are not, yet."
    elif pc and pc.get("publishable") and pc.get("known") and not pc.get("with_presence"):
        body.append(f"None of your {pc['known']} closest Indian peers has a team in Europe yet: the first to move sets the terms.")
    if best:
        v, p = best["view"], best["product"]
        body.append(f"Europe imports {eur_range(v['extra_eu'])} a year of {p['name'].lower()} from outside the EU"
                    + (f", and Indian suppliers already hold {pct_range(v['india_share'], 1 if v['india_share'] < 0.05 else 5)}"
                       if v.get("india_share") else "") + ".")
        gi, gm = v.get("india_growth"), v.get("extra_eu_growth")
        if gi is not None and gm is not None and gi > gm + 0.01:
            body.append(f"India's sales here are growing faster than the market, about {pct_range(gi)} a year.")
        if best.get("tariff") and best["tariff"]["rate"] > 0:
            body.append(f"You pay Europe's standard {best['tariff']['rate']:g}% tariff until the EU–India agreement is in force.")
    elif a.offering and a.offering.kind == "services" and a.buyer_view:
        bv = a.buyer_view
        body.append(f"You sell {a.offering.segment or 'your services'} to an industry that produces "
                    f"{eur_range(bv['gva'])} of value a year in Europe.")
    cert = next((d for d in a.ready.dimensions if d.name == "Certification and compliance"), None)
    if cert and cert.points < 15:
        body.append("The certifications European buyers check first are not visible on your website.")
    pv = a.presence.verdict if a.presence else ""
    if pv == "GREENFIELD":
        body.append("You have no European presence yet.")
    elif pv == "EXPORTING":
        body.append("You reach European buyers today without a base there.")
    elif pv == "ESTABLISHED":
        body.append("You already have a base in Europe; the question is how far to take it.")
    c = a.competitors
    if _strong(c) and not (a.presence and a.presence.verdict == "ESTABLISHED"):
        headline = "Your competitors are already selling in Europe. You are not, yet."
    if _strong(c):
        body.insert(0,
                    f"{c['in_europe']} companies selling what you sell already have teams in Europe"
                    + (f", and {c['indian_in_europe']} of them run most of their work from India like you"
                       if c.get("indian_in_europe") else "") + ".")
    if len(body) < 2:
        return None
    close = ("Every month the gap stays open, buyers sign with suppliers who are ready."
             if rd < 55 else "Those who move before the tariff falls set the terms for those who follow.")
    return {"headline": headline, "body": " ".join(body[:5]), "close": close}


def _competitor_panel(a) -> dict | None:
    c = a.competitors
    if not c or not c.get("in_europe"):
        return None
    seg = a.offering.segment if a.offering and a.offering.segment else "what you sell"
    n = c["in_europe"]
    b = [(f"We found **1 company selling {seg}** that already has a team in Europe, " if n == 1 else
          f"We found **{n} companies selling {seg}** that already have teams in Europe, ")
         + f"with at least **{c['europe_people']:,} people** there."]
    if c.get("recent_people"):
        b.append(f"**{c['recent_people']:,}** of those people started their roles in the last 12 months: "
                 + ("this competitor is hiring in Europe now." if n == 1 else "your competitors are hiring in Europe now."))
    if c.get("indian_in_europe"):
        k = c["indian_in_europe"]
        if n == 1:
            lead, verb = "**It runs most of its team from India**", "sells"
        elif k == 1:
            lead, verb = "**1 of them runs most of its team from India**", "sells"
        else:
            lead, verb = f"**{k} of them run most of their teams from India**", "sell"
        b.append(f"{lead}, the same cost base you have, and already {verb} to European buyers.")
    b.append("Which company it is is in your emailed report." if n == 1 else
             "Which companies they are is in your emailed report.")
    title = ("Your competitors are already in Europe" if _strong(c) else
             "A competitor is already in Europe" if n == 1 else "Some of your competitors are already in Europe")
    return {"title": title, "tone": "red", "bullets": b}


def _evidence(a) -> list[dict]:
    panels = []
    comp = _competitor_panel(a)
    if comp:
        panels.append(comp)
    p = a.presence
    if p:
        b = []
        if p.europe_people:
            top = sorted(p.by_country.items(), key=lambda x: -x[1])[:3]
            b.append(f"**{p.europe_people} people** based in Europe on public profiles"
                     + (f", most in {', '.join(f'{ref_name(c)} ({n})' for c, n in top)}" if top else "") + ".")
        if p.commercial:
            b.append(f"**{p.commercial}** of them in sales or business development roles.")
        if p.eu_domains:
            b.append(f"A European site linked from yours: **{p.eu_domains[0]}**.")
        if p.countries_on_site:
            b.append(f"Your site names **{len(p.countries_on_site)} European markets**.")
        if not b:
            b.append("We found **no European staff, entity or markets** in public sources.")
        panels.append({"title": "Your Europe presence today", "tone": "blue", "bullets": b})
    t = []
    best = max((d for d in a.demand if d["view"]), key=lambda d: d["view"]["extra_eu"], default=None)
    t.append("EU–India trade negotiations **concluded in January 2026**; until the agreement is in force, "
             "Europe's standard tariffs apply" + (f", today **{best['tariff']['rate']:g}%** on your product." if best and best.get("tariff") else "."))
    t.append("The **UK–India agreement has applied since 15 July 2026**.")
    groups = {pr.get("group") for pr in (a.offering.products if a.offering else [])}
    if groups & {"eng_steel", "eng_steelart"}:
        t.append("Europe's **carbon border tax (CBAM)** applies to your steel products: certificates go on sale on **1 February 2027**.")
        t.append("Steel imports above Europe's quota pay **50% duty since 1 July 2026**.")
    if groups & {"tex_leather", "tex_footwear"}:
        t.append("The EU **deforestation rules apply to cattle leather from 30 December 2026**.")
    buyers = set(a.offering.buyers) if a.offering else set()
    if buyers & {"A01", "A02", "A03", "C10-C12", "C16"}:
        t.append("In your buyers' industry, the EU **deforestation rules apply from 30 December 2026**: cattle, cocoa, "
                 "coffee, palm oil, rubber, soy and wood must be traced to the plot of land they came from, "
                 "so traceability is becoming a requirement, not an option.")
    if buyers & {"K64", "K65", "K66"}:
        t.append("Your European financial clients must hold IT suppliers to **DORA**, in force since 17 January 2025.")
    if a.financials and isinstance(a.financials.get("op_margin"), (int, float)) and isinstance(a.financials.get("op_margin_prev"), (int, float)) \
            and a.financials["op_margin"] < a.financials["op_margin_prev"]:
        t.append(f"Your operating margin fell in FY{a.financials['year']}: new markets matter more.")
    panels.append({"title": "Your timing is not neutral", "tone": "orange", "bullets": t})
    c = []
    cert = next((d for d in a.ready.dimensions if d.name == "Certification and compliance"), None)
    if cert:
        c.append(cert.basis)
    reg = next((d for d in a.ready.dimensions if d.name == "Regulatory exposure handled"), None)
    if reg and reg.points > 0:
        c.append(reg.basis)
    if a.offering and a.offering.products:
        told = getattr(a, "offering_source", None) == "visitor"
        c.append(("From the products you told us, we matched: " if told else "We matched your products to: ")
                 + "; ".join(f"**{pr['name']}** (HS {pr['hs']})" for pr in a.offering.products[:3])
                 + (". You can change them below." if told else ". Tell us if a match is wrong."))
    panels.append({"title": "What European buyers will check", "tone": "red", "bullets": c})
    return panels


def ref_name(code: str) -> str:
    from app.signals.europe_presence import COUNTRIES
    return COUNTRIES.get(code, code)


def preview(stage: str, a) -> dict:
    """What the page shows while the rest of the check runs. Same rules as the
    full page: ranges only, nothing unverified, no third-party names."""
    out: dict = {"stage": stage, "company": _company(a)}
    if stage == "products":
        if a.offering is None:
            out["products"] = []
        else:
            told = getattr(a, "offering_source", None) == "visitor"
            out["products_source"] = "visitor" if told else "site"
            out["products"] = [
                {"name": d["product"]["name"],
                 "demand": (f"{eur_range(d['view']['extra_eu'])} a year imported from outside the EU"
                            if d["view"] and d["view"].get("extra_eu") else None)}
                for d in a.demand]
            if not a.demand and a.offering.services:
                out["products"] = [{"name": s["name"], "demand": None} for s in a.offering.services[:3]]
            out["segment"] = a.offering.segment
    return out


def build(a) -> dict:
    base = {
        "engine": "europe",
        "company": _company(a),
        "disclaimer": ("This assessment was generated from public sources: company websites, annual reports, "
                       "Eurostat and World Bank trade data, and professional profiles. Figures carry the year of "
                       "their source. Where we could not verify something, we left it out rather than estimating "
                       "it. Ranges are indicative and are not an offer or a quotation. Nothing here is a statement "
                       "about the conduct of any named third party."),
    }
    if a.offering:
        base["products_named"] = ([p["name"] for p in a.offering.products[:3]]
                                  or [s["name"] for s in a.offering.services[:3]])
        base["products_source"] = getattr(a, "offering_source", None) or "site"
    if a.offering is None and not a.reachable and not (a.org or a.presence and a.presence.europe_people):
        base["mode"] = "NOT_READ"
        base["message"] = ("We could not read your website" + (" (it blocks automated readers)." if a.site_note and "blocked" in a.site_note else ".")
                           + " Tell us what you sell and we will complete the assessment.")
        base["lead_capture"] = {"type": "complete_the_picture", "field": "work_email",
                                "title": "Get your Europe market case in two weeks",
                                "offer": "We build it with you against your own products and numbers. No obligation."}
        return base
    if a.offering is None:
        # Without knowing what they sell, any market score would be invented:
        # show what we found about their presence and ask instead.
        base["mode"] = "NO_OFFERING"
        base["europe_status"] = a.presence.reason if a.presence else None
        base["message"] = ("We could not tell from your website what you sell, so we have not scored Europe's "
                           "market for it. Tell us your main products and we will complete the assessment.")
        base["own_evidence"] = [e for e in _evidence(a) if e["title"] == "Your Europe presence today"]
        base["withheld"] = WITHHELD
        base["lead_capture"] = {"type": "complete_the_picture", "field": "work_email",
                                "title": "Get your Europe market case in two weeks",
                                "offer": "We build it with you against your own products and numbers. No obligation."}
        return base
    base["mode"] = "STANDARD"
    base["europe_status"] = a.presence.reason if a.presence else None
    comp_card = _competitor_card(a)
    base["peer_headline"] = comp_card or _peer(a)
    base["summary"] = _summary(a, None if comp_card else base["peer_headline"])
    base["market"] = _card(a.market, "Is Europe a market for what you sell?",
                           "Indicative. Based on Eurostat trade data for your products and World Bank tariff data; "
                           "the full business case tests it against your own buyers.", "insight")
    base["readiness"] = _card(a.ready, "Are you ready to sell in Europe today?",
                              "Based on your own website, annual report and public professional profiles.", "reason")
    base["countries"] = [{"code": c["code"], "name": c["name"], "why": c["why"]} for c in a.countries]
    base["uk_note"] = a.uk_note
    base["time_to_first_order"] = a.time_range
    base["own_evidence"] = _evidence(a)
    # Names of competitors: kept with the run on the server for the emailed
    # PDF; the API strips "_private" before anything reaches the page.
    if a.competitors and a.competitors.get("named"):
        base["_private"] = {"competitors": a.competitors["named"],
                            "competitor_segment": a.offering.segment if a.offering else None}
    base["withheld"] = WITHHELD
    base["lead_capture"] = {
        "type": "bdaas", "field": "work_email",
        "title": "We become your European team",
        "offer": ("Airopa Global sells under your brand in Europe from day one, while you decide on an entity. "
                  "The first step is a two-week Europe market-entry business case, built against your own "
                  "products and numbers. No obligation."),
    }
    return base
