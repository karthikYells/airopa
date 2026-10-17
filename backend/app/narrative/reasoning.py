"""Public reasoning for each score dimension (Sections 8.2, 8.3, 9.1).

Each dimension gets a short paragraph in three parts: what the evidence shows,
what it means for this company, and what keeps it from the top band (or what
the full business case would test). Figures appear only as ranges ("counts,
shares and ranges" are shown, Section 9.1); exact reference values, points and
third-party names stay in the engine. Every sentence is built from a resolved
signal; nothing is written where the signal is missing.
"""
from __future__ import annotations

import math

from app.data.records import CompanyRecord, DimensionScore
from app.scoring.common import resolved_value


# --- range helpers: a figure is always shown as a band, never a point ----------
def pct_range(v: float, width: int = 5) -> str:
    lo = int(math.floor(v * 100 / width) * width)
    return f"{lo} to {lo + width}%"


def eur_range(v: float) -> str:
    bn = v / 1e9
    if bn >= 1:
        if bn < 5:
            lo = math.floor(bn)
            return f"EUR {lo} to {lo + 1}bn"
        lo = math.floor(bn / 5) * 5
        return f"EUR {lo} to {lo + 5}bn"
    m = v / 1e6
    lo = math.floor(m / 100) * 100
    return f"EUR {lo} to {lo + 100}m"


def weeks_range(w: int) -> str:
    return f"{max(1, w - 2)} to {w} weeks" if w <= 10 else f"{w - 4} to {w} weeks"


def months_range(m: int) -> str:
    return f"{max(1, m - 2)} to {m} months"


def _count(n: int) -> str:
    if n >= 100_000:
        return f"over {math.floor(n / 50_000) * 50_000:,}"
    if n >= 10_000:
        return f"over {math.floor(n / 5_000) * 5_000:,}"
    return f"around {n:,}"


def _top(d: DimensionScore, top_from: float) -> bool:
    return d.points >= top_from


def _v(rec: CompanyRecord, sid: str):
    return resolved_value(rec, sid)


_THE = {"Netherlands", "United Kingdom", "United States", "Czech Republic"}


def _home(rec: CompanyRecord) -> str:
    j = rec.jurisdiction
    if not j:
        return "your home market"
    return f"the {j}" if j in _THE else j


def _sector(rec: CompanyRecord) -> str:
    return (rec.sector or "your sector").lower()


# --- India Market Opportunity ----------------------------------------------------
def _demand(rec, d):
    size, growth, down = _v(rec, "DEM.02"), _v(rec, "DEM.03"), _v(rec, "DEM.13")
    if not isinstance(size, (int, float)) or not isinstance(growth, (int, float)):
        return ""
    out = (f"India's market for {_sector(rec)} is in the range of {eur_range(size)}, "
           f"growing roughly {pct_range(growth)} a year")
    out += (f", with the industries that buy from you growing {pct_range(down)}."
            if isinstance(down, (int, float)) and down > 0 else ".")
    if _top(d, 21):
        out += " A market measured in billions, growing at double digits, is the top band."
    else:
        out += " Real and growing, but not yet large and fast enough for the top band."
    return out + (" This is sector level; sizing India demand for your exact products is "
                  "part of the full business case.")


def _fit(rec, d):
    present, price, adapt = _v(rec, "DEM.05"), _v(rec, "DEM.06"), _v(rec, "DEM.07")
    if present is None:
        return ""
    if present is False:
        return ("The buyers your sector sells to are not yet present in India at scale, "
                "so your products would need a different segment.")
    price_txt = {"strong": "Price points in your category work in India",
                 "moderate": "Indian buyers in your category pay less, so a price tier is often needed",
                 "weak": "Indian price points in your category sit well below European levels"}
    adapt_txt = {"minimal": "products sell with minimal adaptation",
                 "moderate": "products usually need a local variant",
                 "heavy": "products need substantial adaptation"}
    parts = [x for x in (price_txt.get(str(price)), adapt_txt.get(str(adapt))) if x]
    out = "Buyers like yours exist in India at scale."
    if parts:
        tail = " and ".join(parts) if len(parts) == 2 else parts[0]
        out += " " + tail[0].upper() + tail[1:] + "."
    if not parts:
        out += " How well your price points and products fit Indian buyers is not yet evidenced, which holds this score down."
    elif not _top(d, 17):
        out += " That need for a variant or price tier keeps this below the top band."
    return out + " Which of your product lines translate is tested in the full case."


def _competition(rec, d):
    peers, entrants = _v(rec, "DEM.11"), _v(rec, "DEM.14")
    if peers is None and entrants is None:
        return ""
    bits = []
    if peers:
        bits.append("European companies in your sector already report revenue from India")
    if entrants:
        bits.append("foreign entrants have built positions in your category")
    out = (" and ".join(bits) + ".") if bits else "We found no evidence of peers earning revenue in India."
    out = out[0].upper() + out[1:]
    out += (" That shows the market rewards companies like yours rather than closing to them."
            if bits else "")
    return out + (" The top band also needs evidence that the premium end of your category is "
                  "open, which depends on your specific products.")


def _policy(rec, d):
    pli, fdi, tariff = _v(rec, "POL.01"), _v(rec, "POL.02"), _v(rec, "DEM.08")
    trade = (_v(rec, "POL.06") or {}).get("trade_agreement") if isinstance(_v(rec, "POL.06"), dict) else None
    local = _v(rec, "DEM.09")
    if pli is None and fdi is None:
        return ""
    s = []
    if pli:
        s.append("Your sector is named in India's production-linked incentive (PLI) schemes")
    if fdi == "automatic":
        s.append("foreign companies can invest without prior government approval (automatic route)")
    elif fdi == "approval":
        s.append("foreign investment in your sector needs prior government approval")
    if tariff == "favourable":
        s.append("import tariffs favour companies that make or assemble locally")
    elif tariff == "adverse":
        s.append("import tariffs work against your category")
    out = "; ".join(s) + "." if s else ""
    out = out[0].upper() + out[1:] if out else out
    if local:
        out += " Public buyers in India give preference to locally made products."
    if trade:
        out += f" Trade: {trade}."
    return out.strip()


def _route(rec, d):
    route = (_v(rec, "DEM.15") or {}).get("route") if isinstance(_v(rec, "DEM.15"), dict) else None
    months = (_v(rec, "DEM.16") or {}).get("approval_lead_months") if isinstance(_v(rec, "DEM.16"), dict) else None
    own = _v(rec, "GATE.01") is True
    s = []
    if route == "established":
        s.append("Distributors and partners for your sector are well established in India")
    elif route == "partial":
        s.append("Some distribution exists for your sector, but partners need to be built")
    elif route == "none":
        s.append("There is no established distribution route for your sector yet")
    if isinstance(months, int):
        s.append(f"product approvals and certification typically take {months_range(months)}")
    out = ", and ".join(s) + "." if s else ""
    if own:
        out += " Your existing India presence gives you a base to sell from."
    else:
        out += (" You have no India presence of your own yet, which holds this below the top "
                "band; the full case sets out the entry model, from distributor to own entity.")
    return out.strip()


def _supply_chain(rec, d):
    c1, named = _v(rec, "POL.07"), _v(rec, "POL.08")
    if c1 is None or c1 == "n/a":
        return ""
    txt = {"strong": "Your sector is part of the shift of manufacturing and sourcing into India (China plus one)",
           "relevant": "Your sector is touched by the shift of supply chains into India (China plus one)",
           "weak": "The shift of supply chains into India has limited relevance to your sector"}
    out = txt.get(str(c1), "") + "."
    if named:
        out += " Companies across your sector's supply chains are already moving production to India."
    return out + (" The top band needs named customers or suppliers of yours relocating, "
                  "which the full case identifies.")


# --- Technology Hub Readiness ------------------------------------------------------
def _talent(rec, d):
    depth, growth, grads = _v(rec, "TAL.02"), _v(rec, "TAL.03"), _v(rec, "TAL.04")
    stack = _v(rec, "TAL.01")
    if depth is None:
        return ""
    depth_txt = {"very_deep": "very deep", "deep": "deep", "moderate": "moderate", "shallow": "thin"}
    out = f"India's talent pool for {_sector(rec)} engineering is {depth_txt.get(str(depth), str(depth))}"
    if isinstance(growth, (int, float)):
        out += f", growing about {pct_range(growth)} a year"
    if isinstance(grads, int) and grads > 0:
        out += f", with {_count(grads)} relevant graduates a year"
    out += "."
    if isinstance(stack, list) and stack:
        out += (f" Your own site shows {', '.join(map(str, stack[:4]))}, which India supplies at depth.")
    else:
        out += (" We could not see your technology stack on your site, so this is sector "
                "level; the full case matches it to the roles you cannot fill.")
    return out


def _cost(rec, d):
    india, home = _v(rec, "TAL.09"), _v(rec, "TAL.10")
    if not isinstance(india, (int, float)) or not isinstance(home, (int, float)) or not home:
        return ""
    saving = 1 - india / home
    out = (f"Fully loaded, comparable engineering roles cost about {pct_range(saving, 10)} "
           f"less in India than in {_home(rec)}.")
    if _v(rec, "COST.02") is None:
        out += (" We did not find work you already outsource, so this is the saving on new "
                "roles; outsourced scope brought in-house would add to it.")
    return out + " A costed team against your own salary bands is part of the full case."


def _ip(rec, d):
    strength = _v(rec, "IPR.30")
    if strength in (None, "none"):
        return ""
    ev = rec.get("IPR.30")
    sector_only = ev is not None and ev.source_type is not None and ev.source_type.value == "reference_data"
    out = f"Your sector is {'highly ' if strength == 'high' else ''}IP-intensive."
    if sector_only:
        out += (" We have not yet resolved your own patents or which outside firms work on "
                "your engineering, so this scores low for now. It scores high only where real "
                "IP is exposed to third parties today and an owned team would take it back.")
    return out


def _velocity(rec, d):
    india, home = _v(rec, "TAL.06"), _v(rec, "TAL.07")
    own = _v(rec, "HIRE.06")
    out = ""
    if isinstance(india, int) and isinstance(home, int):
        out = (f"Comparable roles take around {weeks_range(india)} to fill in India against "
               f"{weeks_range(home)} in {_home(rec)}.")
    if isinstance(own, (int, float)) and own >= 90:
        out += (f" Half of the roles on your own careers site have been open at least "
                f"{int(own)} days, which is where the gap becomes a cost.")
    elif out:
        out += (" We have not yet watched your own vacancies long enough to measure how long "
                "they stay open; that is what lifts this to the top band.")
    return out.strip()


def _precedent(rec, d):
    prec = _v(rec, "TAL.15")
    txt = {"strong": "Engineering for your sector is already delivered from India at scale, by "
                     "European peers and by service firms, so the model is proven rather than novel.",
           "adjacent": "Adjacent sectors already deliver engineering from India; for your own "
                       "sector the model is newer.",
           "weak": "Few companies in your sector deliver engineering from India yet.",
           "none": "We found no precedent for delivering your sector's engineering from India."}
    return txt.get(str(prec), "")


def _sovereignty(rec, d):
    sov2 = _v(rec, "SOV.02")
    restriction = sov2.get("restriction") if isinstance(sov2, dict) else sov2
    share = _v(rec, "SOV.03")
    if restriction is None and share is None:
        return ""
    if restriction and str(restriction).lower() not in ("none", "none material"):
        out = f"Your sector carries {restriction}, which limits part of the scope that can move."
    else:
        out = "We found no data residency, export-control or defence constraints for your sector."
    if _v(rec, "SOV.08") is True:
        out += (" Personal data can move to India under standard EU contract clauses (GDPR), "
                "which is routine.")
    return out


def _location(rec, d):
    cities, attrition, density = _v(rec, "TAL.12"), _v(rec, "TAL.08"), _v(rec, "TAL.16")
    if not cities:
        return ""
    out = f"The strongest cities for your sector are {', '.join(map(str, cities[:3]))}"
    if isinstance(attrition, (int, float)):
        out += f", where annual attrition runs around {pct_range(attrition, 4)}"
    out += "."
    if isinstance(density, int) and density > 0:
        out += " Each has a dense base of capability centres and service firms to hire from."
    if _v(rec, "GATE.01") is True:
        out += " Your existing India footprint shortens set-up."
    else:
        out += " Which city fits you best is part of the full case."
    return out


_FUNCS = {
    "Addressable demand": _demand, "Product and segment fit": _fit,
    "Competitive position": _competition, "Policy and incentives": _policy,
    "Route to market": _route, "Supply chain and China plus one": _supply_chain,
    "Talent pool depth for their stack": _talent, "Cost arbitrage": _cost,
    "IP control and security": _ip, "Hiring velocity": _velocity,
    "Sector delivery precedent": _precedent, "Sovereignty and data risk": _sovereignty,
    "Location and infrastructure fit": _location,
}


def reason_for(rec: CompanyRecord, d: DimensionScore) -> str:
    f = _FUNCS.get(d.name)
    try:
        return f(rec, d) if f else ""
    except Exception:
        return ""


# --- Indicative scale (block 6): ranges only (Section 9.1) ----------------------------
def indicative_scale(rec: CompanyRecord) -> dict | None:
    """First phase team, saving and time to first team, each a wide range built
    from their own headcount, the salary benchmark (COST.05) and whether they
    already have an India entity. None if the inputs are missing."""
    india, home = _v(rec, "TAL.09"), _v(rec, "TAL.10")
    hc = _v(rec, "SCALE.04")
    if not isinstance(india, (int, float)) or not isinstance(home, (int, float)) or not home:
        return None
    if not isinstance(hc, int) or hc <= 0:
        return None
    mid = min(60, max(10, round(hc * 0.0075)))
    lo, hi = max(5, math.floor(mid * 0.8 / 5) * 5), math.ceil(mid * 1.25 / 5) * 5
    saving = 1 - india / home
    has_entity = _v(rec, "GATE.01") is True
    return {
        "first_phase_team": f"{lo} to {hi} people",
        "team_basis": "sized on your headcount",
        "indicative_saving": pct_range(saving, 10),
        "saving_basis": f"on the fully loaded cost of comparable roles in {_home(rec)}",
        "time_to_first_team_live": "About 100 days" if has_entity else "4 to 6 months",
        "time_basis": ("your India entity already exists" if has_entity
                       else "including setting up an entity or an employer of record"),
        "note": "Ranges only, not an offer or a quotation. Your actual numbers depend on scope.",
    }
