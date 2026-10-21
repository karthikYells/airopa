"""Europe Market Assessment scores (spec v1.1 sections 6 and 7).

Score A, Europe Market Opportunity: is there demand in Europe for what they
sell, and are the terms of trade in their favour?
Score B, Europe Readiness: are they ready to sell in Europe today?

Each dimension returns points (engine only) and a reason for the public page.
Reasons use ranges and the company's own facts; a dimension with no evidence
scores 0 and says "not resolved" rather than guessing. Goods and services use
the same dimension names with different inputs.
"""
from __future__ import annotations

import math
import re

from app.data.records import DimensionScore, ScoreResult
from app.narrative.reasoning import eur_range, pct_range
from app.scoring.bands import band_for

# --- certifications by sector (Score B) ----------------------------------------------
CERTS = {
    "ISO 9001": r"ISO\s?9001", "ISO 14001": r"ISO\s?14001", "ISO 45001": r"ISO\s?45001",
    "IATF 16949": r"IATF\s?16949|TS\s?16949", "CE marking": r"\bCE[- ]mark|\bCE[- ]certif|\bCE[- ]compliant|\bCE[- ]approved",
    "AS9100": r"AS\s?9100", "EU GMP": r"EU[- ]GMP|EU GMP|EDQM|CEP\b|certificate of suitability",
    "GMP": r"\bc?GMP\b|WHO[- ]GMP", "REACH": r"\bREACH\b", "ISO 27001": r"ISO\s?27001|ISO/IEC\s?27001",
    "SOC 2": r"SOC\s?2", "GDPR statement": r"\bGDPR\b", "OEKO-TEX": r"OEKO[- ]?TEX", "GOTS": r"\bGOTS\b|Global Organic Textile",
    "BSCI / Sedex / SA8000": r"amfori|BSCI|SEDEX|SMETA|SA\s?8000", "Leather Working Group": r"Leather Working Group|\bLWG\b",
    "EcoVadis": r"EcoVadis", "GDPR": r"\bGDPR\b",
}
REQUIRED = {
    "engineering_auto": ["ISO 9001", "ISO 14001", "IATF 16949", "CE marking"],
    "chemicals_pharma": ["ISO 9001", "ISO 14001", "REACH", "EU GMP"],
    "textiles_apparel_leather": ["OEKO-TEX", "GOTS", "BSCI / Sedex / SA8000", "ISO 9001"],
    "it_services": ["ISO 27001", "SOC 2", "ISO 9001", "GDPR statement"],
}
# What "handling" each regulation looks like on a company's own pages.
REG_EVIDENCE = {
    "CBAM": r"\bCBAM\b|carbon border|embedded emissions|product carbon footprint",
    "REACH": r"\bREACH\b|only representative|ECHA",
    "EUDR": r"\bEUDR\b|deforestation[- ]free|traceab",
    "GDPR": r"\bGDPR\b|standard contractual clauses|data protection",
    "Sustainability reporting": r"sustainability report|ESG report|BRSR|EcoVadis|science based targets|SBTi",
}
REG_EVIDENCE["Textile chemicals (REACH)"] = r"REACH|OEKO[- ]?TEX|ZDHC|restricted substances|RSL"
REG_EVIDENCE["Ecodesign and unsold goods"] = r"ecodesign|ESPR|circular|recycl|digital product passport"
# Rules follow the product groups they apply to (reference v1 rules).
REG_BY_GROUP = {
    "eng_steel": ["CBAM"], "eng_steelart": ["CBAM"], "eng_mach": [], "eng_auto": [],
    "chem_inorg": ["REACH"], "chem_org": ["REACH"], "chem_dyes": ["REACH"], "chem_misc": ["REACH"],
    "chem_pharma": [], "tex_fabric": ["Textile chemicals (REACH)"],
    "tex_apparel": ["Textile chemicals (REACH)", "Ecodesign and unsold goods"],
    "tex_madeups": ["Textile chemicals (REACH)"], "tex_leather": ["EUDR", "Textile chemicals (REACH)"],
    "tex_footwear": ["EUDR", "Ecodesign and unsold goods"],
}


def regs_for(a) -> list[str]:
    """The EU rules that apply to what this company sells, plus sustainability
    reporting, which large European buyers ask every supplier about."""
    out: list[str] = []
    if a.offering:
        for p in a.offering.products:
            for r in REG_BY_GROUP.get(p.get("group") or "", []):
                if r not in out:
                    out.append(r)
        # Personal-data rules bite on IT and data services, not on design or BPO lines of a manufacturer.
        if a.offering.kind == "services" or any(s["code"] == "SI" for s in a.offering.services) and not a.offering.products:
            out.append("GDPR")
    return out + ["Sustainability reporting"] if (a.offering and (a.offering.products or a.offering.services)) else []
_EU_LANGS = {"de", "fr", "nl", "it", "es", "pl", "sv", "cs", "pt", "da", "fi"}


def find_certs(text: str) -> list[str]:
    return [name for name, pat in CERTS.items() if re.search(pat, text or "")]


def _ratio(dims) -> float:
    return sum(d.points for d in dims) / sum(d.max_points for d in dims) if dims else 0.0


def _result(key, label, dims) -> ScoreResult:
    # Scored out of 100 even when a dimension does not apply (services have no
    # China dimension): points are scaled to the dimensions that do apply.
    mx = sum(d.max_points for d in dims)
    pts = round(sum(d.points for d in dims) * (100 / mx if mx else 1), 1)
    resolved = sum(1 for d in dims if d.points > 0)
    return ScoreResult(key=key, label=label, points=pts, band=band_for(pts),
                       coverage=resolved / len(dims) if dims else 0.0,
                       confidence=0.6, dimensions=dims,
                       applicable_signals=len(dims), resolved_signals=resolved)


# --- Score A: Europe Market Opportunity ----------------------------------------------------
def _best(demand: list[dict]) -> dict | None:
    rows = [d for d in demand if d.get("view")]
    return max(rows, key=lambda d: d["view"]["extra_eu"]) if rows else None


def market_opportunity(a) -> ScoreResult:
    """`a` is the EuropeAssessment being built (pipeline.europe)."""
    if a.offering and a.offering.kind == "services":
        return _market_services(a)
    best = _best(a.demand)
    dims = []
    name = "Addressable demand"
    if not best:
        dims.append(DimensionScore(name, 0, 25, "Not resolved: we could not match your products to European trade data."))
    else:
        v, prod = best["view"], best["product"]
        size, g = v["extra_eu"], v.get("extra_eu_growth") or 0.0
        if size >= 1e9 and g >= 0.05:
            pts = 21 + min(4, (g - 0.05) * 40)
        elif size >= 2.5e8 and g >= 0:
            pts = 15 + min(5, g * 100)
        elif size > 0:
            pts = 8 + min(6, max(0, g) * 60 + size / 2.5e8 * 4)
        else:
            pts = 3
        basis = "the wider product group" if v.get("basis") == "heading" else "your product"
        dims.append(DimensionScore(name, round(min(25, pts), 1), 25,
            f"Europe imports {eur_range(size)} a year of {prod['name'].lower()} ({basis}, HS {v['hs']}) from outside the EU, "
            f"{'growing' if g >= 0 else 'shrinking'} roughly {pct_range(abs(g))} a year."))
    # Product fit: Europe already buys this product from India.
    name = "Product and segment fit"
    if not best or best["view"].get("india_share") is None:
        dims.append(DimensionScore(name, 0, 20, "Not resolved."))
    else:
        sh = best["view"]["india_share"]
        pts = 18 if sh >= 0.05 else 14 if sh >= 0.02 else 10 if sh >= 0.005 else 7
        dims.append(DimensionScore(name, pts, 20,
            f"Indian suppliers already provide {pct_range(sh, 1 if sh < 0.05 else 5)} of what Europe imports here, "
            + ("so European buyers know Indian quality in your product." if sh >= 0.02 else
               "so Indian supply is still unusual here: an opening, but you will need to prove quality.")))
    # Competitive position: India gaining or losing share; China's weight.
    name = "Competitive position"
    if not best or best["view"].get("india_growth") is None:
        dims.append(DimensionScore(name, 0, 15, "Not resolved."))
    else:
        v = best["view"]
        gi, gm, cn = v["india_growth"], v.get("extra_eu_growth") or 0.0, v.get("china_share") or 0.0
        gaining = gi > gm + 0.01
        pts = (14 if gaining and v["india_share"] >= 0.05 else 12 if gaining else 9 if gi >= gm - 0.03 else 6)
        if cn >= 0.5 and not gaining:
            pts = 4
        dims.append(DimensionScore(name, pts, 15,
            f"India's sales here are {'growing' if gi >= 0 else 'falling'} about {pct_range(abs(gi))} a year against "
            f"{pct_range(abs(gm))} for the market, so India is {'gaining' if gaining else 'not gaining'} share. "
            f"China supplies {pct_range(cn, 5)}."))
    # Tariffs and trade terms.
    name = "Tariffs and trade terms"
    tar = best.get("tariff") if best else None
    if not tar:
        dims.append(DimensionScore(name, 0, 15, "Not resolved: tariff data for your product was not available."))
    else:
        r = tar["rate"]
        pts = 13 if r == 0 else 11 if r <= 4 else 8 if r <= 8 else 5
        pts = min(15, pts + 1)   # UK–India agreement in force since 15 July 2026
        dims.append(DimensionScore(name, pts, 15,
            f"Europe's standard tariff on your product is {r:g}% ({tar['year']}). "
            + ("Tariffs this high are what the EU–India agreement is expected to remove. " if r > 4 else "")
            + "In the UK, the UK–India agreement has applied since 15 July 2026."))
    dims.append(_route(a))
    # Europe's shift away from China.
    name = "Europe's shift away from China"
    if not best or best["view"].get("china_share") is None:
        dims.append(DimensionScore(name, 0, 10, "Not resolved."))
    else:
        v = best["view"]
        cn, gaining = v["china_share"], (v.get("india_growth") or 0) > (v.get("extra_eu_growth") or 0)
        pts = 8 if cn >= 0.3 and gaining else 6 if cn >= 0.3 else 4
        dims.append(DimensionScore(name, pts, 10,
            f"China supplies {pct_range(cn, 5)} of Europe's imports of your product. "
            + ("European buyers diversifying away from China are a real opening for you, and India is already gaining."
               if cn >= 0.3 and gaining else
               "European buyers diversifying away from China are an opening." if cn >= 0.3 else
               "China is not the main supplier here, so diversification matters less.")))
    return _result("europe_market", "Europe Market Opportunity", dims)


def _route(a) -> DimensionScore:
    p = a.presence
    pts = {"ESTABLISHED": 13, "EXPORTING": 10, "GREENFIELD": 6}.get(p.verdict if p else "", 0)
    text = {
        "ESTABLISHED": "You already have a base in Europe, so the route to buyers exists.",
        "EXPORTING": "You already reach European buyers without a local base; a base is the next step.",
        "GREENFIELD": "You have no European presence yet, so a distributor, partner or own team is the first step.",
    }.get(p.verdict if p else "", "Not resolved: too little data on your European presence.")
    return DimensionScore("Route to market", pts, 15, text)


def _market_services(a) -> ScoreResult:
    """Services: demand is the EU industry that buys from them (Eurostat value
    added), not the whole services category. It stands in for their segment's
    market, so it is capped below the top band and says so."""
    off = a.offering
    seg = off.segment if off and off.segment else "what you sell"
    bv = a.buyer_view
    dims = []
    if bv:
        size, g = bv["gva"], bv.get("growth") or 0.0
        pts = 20 if size >= 5e11 and g >= 0.04 else 17 if size >= 2e11 else 13 if size >= 5e10 else 9
        dims.append(DimensionScore("Addressable demand", pts, 25,
            f"Your buyers are in {_join([l.split(',')[0].lower() for l in bv['labels']])}: in Europe these industries "
            f"produce {eur_range(size)} of value a year ({bv['year']}), "
            f"{'growing' if g >= 0 else 'shrinking'} about {pct_range(abs(g))} a year. That is the industry you sell to; "
            f"the market for {seg} within it is a niche, and sizing it is part of the business case."))
    else:
        dims.append(DimensionScore("Addressable demand", 0, 25,
            "Not resolved: we could not tell which European industries buy what you sell."))
    vertical = bool(off and off.buyers)
    dims.append(DimensionScore("Product and segment fit", 14 if vertical else 10, 20,
        (f"You specialise in {seg} for one industry, which European buyers prefer to generalists. "
         if vertical else f"You offer {seg} across industries. ")
        + "How well it fits European buyers' workflows and rules is tested in the business case."))
    code_rows = {r["code"]: r for r in a.services}
    codes = [s_["code"] for s_ in off.services] if off else []
    main = code_rows.get(max(set(codes), key=codes.count)) if codes else None
    if main:
        gi, gm = main["in_cagr"], main["ext_cagr"]
        gaining = gi > gm + 0.01
        dims.append(DimensionScore("Competitive position", 12 if gaining else 9, 15,
            f"Across all {main['label'][0].lower() + main['label'][1:]}, India's sales to the EU are growing about "
            f"{pct_range(gi)} a year against {pct_range(gm)} for the market, so Indian suppliers are "
            f"{'gaining' if gaining else 'holding'} ground. Who competes in your own segment is part of the business case."))
    else:
        dims.append(DimensionScore("Competitive position", 0, 15, "Not resolved."))
    dims.append(DimensionScore("Tariffs and trade terms", 11, 15,
        "Services carry no tariffs. Personal data needs EU standard contractual clauses (there is no EU adequacy "
        "decision for India). India's social security agreements with 12 EU countries, and the UK's since "
        "15 July 2026, spare your staff double contributions."))
    dims.append(_route(a))
    return _result("europe_market", "Europe Market Opportunity", dims)


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# --- Score B: Europe Readiness ----------------------------------------------------------
def site_read(a) -> bool:
    """Did we actually read their website? A site that loads but needs
    JavaScript to show anything gives almost no text: what we did not see
    is "not resolved", never a weakness."""
    return bool(a.reachable) and len((a.site_text or "").strip()) >= 500


_NOT_READ = "Not resolved: we could not read your website, so we could not check this."


def readiness(a) -> ScoreResult:
    sector = a.offering.sector if a.offering else None
    text = a.site_text or ""
    found = set(a.certs)
    read = site_read(a)
    dims = []
    req = REQUIRED.get(sector or "", [])
    if req and not read and not found and not getattr(a, "report_cert_text", ""):
        dims.append(DimensionScore("Certification and compliance", 0, 30, _NOT_READ))
    elif req:
        have = [c for c in req if c in found]
        miss = [c for c in req if c not in found]
        pts = max(4, round(30 * len(have) / len(req)))
        dims.append(DimensionScore("Certification and compliance", pts, 30,
            (f"Your website or annual report shows {', '.join(have)}. " if have
             else "We did not find the certifications European buyers look for on your website or in your annual report. ")
            + (f"Buyers in your sector also look for {', '.join(miss)}. If you have them, put them where buyers can see them." if miss
               else "That covers what European buyers in your sector look for.")))
    else:
        dims.append(DimensionScore("Certification and compliance", 0, 30, "Not resolved: your products are outside the sectors this version covers."))
    regs = regs_for(a)
    if regs and not read:
        dims.append(DimensionScore("Regulatory exposure handled", 0, 15, _NOT_READ))
    elif regs:
        handled = [r for r in regs if re.search(REG_EVIDENCE[r], text, re.I)]
        pts = max(3, round(15 * len(handled) / len(regs)))
        dims.append(DimensionScore("Regulatory exposure handled", pts, 15,
            f"For what you sell, the EU rules that matter are {', '.join(regs)}. "
            + (f"Your site addresses {', '.join(handled)}." if handled else "Your site does not yet say how you handle them.")))
    else:
        dims.append(DimensionScore("Regulatory exposure handled", 0, 15, "Not resolved."))
    p = a.presence
    pv = p.verdict if p else ""
    dims.append(DimensionScore("Europe presence", {"ESTABLISHED": 18, "EXPORTING": 12, "GREENFIELD": 4}.get(pv, 0), 20,
        (p.reason if p else "Not resolved.")))
    proof = 0
    bits = []
    if p and len(p.countries_on_site) >= 3:
        proof += 8; bits.append(f"your site names {len(p.countries_on_site)} European markets")
    elif p and p.countries_on_site:
        proof += 4; bits.append("your site names European markets")
    if p and p.commercial >= 5:
        proof += 5; bits.append(f"{p.commercial}+ people in sales roles in Europe")
    elif p and p.commercial:
        proof += 3; bits.append("people in sales roles in Europe")
    if p and (p.entity_mentions or p.eu_domains):
        proof += 3; bits.append("a European entity or site")
    dims.append(DimensionScore("European customer proof", min(15, proof), 15,
        ("We found " + ", ".join(bits) + ".") if bits else "We found no European customers, markets or sales staff."))
    langs = [l for l in (p.languages if p else []) if l in _EU_LANGS]
    eu_phone = bool(re.search(r"\+(31|32|33|34|39|44|46|48|49|420)[\s\d]{6,}", text))
    loc = min(10, 2 * len(langs) + (2 if eu_phone else 0) + (2 if p and p.eu_domains else 0))
    if read:
        dims.append(DimensionScore("Localisation and commercial readiness", loc, 10,
            (f"Your site is available in {', '.join(sorted(langs))}" if langs else "Your site is in English only")
            + (", with a European phone number." if eu_phone else ".")))
    else:
        dims.append(DimensionScore("Localisation and commercial readiness", 0, 10, _NOT_READ))
    people = (a.org or {}).get("employees") or (p.total_people if p else 0)
    pts = 10 if people >= 5000 else 8 if people >= 1000 else 6 if people >= 250 else 4 if people >= 50 else (2 if people else 0)
    dims.append(DimensionScore("Scale to deliver", pts, 10,
        f"About {people:,} people, " + ("enough to serve large European buyers." if people >= 1000 else
                                        "enough for mid-sized buyers; large tenders may need a partner." if people >= 250 else
                                        "so start with smaller buyers or a partner.") if people else "Not resolved."))
    return _result("europe_readiness", "Europe Readiness", dims)


def time_to_first_order(a, ready: ScoreResult) -> dict:
    """A wide range, built from presence and the certification gap."""
    pv = a.presence.verdict if a.presence else ""
    services = a.offering is not None and a.offering.kind == "services"
    base = {"ESTABLISHED": (3, 6), "EXPORTING": (6, 9), "GREENFIELD": (9, 15) if not services else (6, 12)}.get(pv, (9, 18))
    cert = next((d for d in ready.dimensions if d.name == "Certification and compliance"), None)
    gap = cert is not None and 0 < cert.points < 15         # an unread site is no known gap
    lo, hi = base[0] + (3 if gap else 0), base[1] + (6 if gap else 0)
    return {"range": f"{lo} to {hi} months",
            "basis": ("you already sell in Europe" if pv in ("ESTABLISHED", "EXPORTING") else "starting without a European base")
                     + (", plus time to close certification gaps" if gap else ""),
            "note": "Indicative range, not a commitment. It depends on your product, buyers and approvals."}


def rank_countries(country_rows: list[dict], presence, services: bool) -> list[dict]:
    """Top 3 from per-country demand rows: {code, name, extra, india, growth}.
    Score: size (log), growth, India's existing share, and their own staff there."""
    out = []
    for r in country_rows:
        if not r.get("extra"):
            continue
        size = math.log10(max(r["extra"], 1e6))
        share = (r.get("india") or 0) / r["extra"]
        growth = r.get("growth") or 0.0
        own = (presence.by_country.get(r["code"], 0) if presence else 0)
        score = size + 1.5 * share + 1.0 * growth + (0.3 if own >= 5 else 0)
        out.append({**r, "india_share": share, "own_staff": own, "score": score})
    out.sort(key=lambda r: -r["score"])
    for r in out:
        why = [f"imports {eur_range(r['extra'])} a year from outside the EU" if r["code"] != "UK" else
               f"imports {eur_range(r['extra'])} a year"]
        if r["india_share"] >= 0.05:
            why.append(f"{pct_range(r['india_share'], 5)} already from India")
        if (r.get("growth") or 0) >= 0.05:
            why.append(f"growing {pct_range(r['growth'])} a year")
        if r["own_staff"]:
            why.append(f"you already have {r['own_staff']} people there")
        r["why"] = ", ".join(why)
    return out[:3]
