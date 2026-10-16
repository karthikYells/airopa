"""Wikidata adapter — free, real firmographics for Tier 0 / scale signals.

Resolves a company by matching its domain against the Wikidata 'official website'
(P856), falling back to a name search with an organisation check. Returns only
what Wikidata actually holds; missing fields stay None (honest UNKNOWN upstream).
Also detects an India subsidiary/location, a real input to the India gate.

Wikidata is strong on sector, country, founding year, parent and subsidiaries,
and on revenue/headcount for listed companies; it is often silent on private
mid-market revenue — which is exactly why those remain UNKNOWN rather than
invented (Section 12).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

_API = "https://www.wikidata.org/w/api.php"
_H = {"User-Agent": "AiropaBot/1.0 (https://airopa.co; public assessment)"}
_TIMEOUT = httpx.Timeout(12.0, connect=6.0)
_INDIA_QID = "Q668"

# instance-of values that indicate a company/organisation
_ORG_QIDS = {"Q4830453", "Q6881511", "Q783794", "Q891723", "Q43229",
             "Q18388277", "Q210167", "Q1589009", "Q2085381"}


@dataclass
class WikidataEntity:
    found: bool = False
    qid: str | None = None
    label: str | None = None
    website: str | None = None
    country: str | None = None
    industry: str | None = None
    inception_year: int | None = None
    employees: int | None = None
    revenue_eur: int | None = None
    revenue_year: str | None = None
    parent: str | None = None
    subsidiaries: list[str] = field(default_factory=list)
    india_subsidiary: bool = False
    matched_by: str = ""


def _get(params: dict) -> dict:
    r = httpx.get(_API, params=params, timeout=_TIMEOUT, headers=_H)
    r.raise_for_status()
    return r.json()


def _labels(qids: list[str]) -> dict[str, str]:
    qids = [q for q in qids if q]
    if not qids:
        return {}
    out: dict[str, str] = {}
    for i in range(0, len(qids), 50):
        chunk = qids[i:i + 50]
        data = _get({"action": "wbgetentities", "ids": "|".join(chunk),
                     "props": "labels", "languages": "en", "format": "json"})
        for qid, ent in data.get("entities", {}).items():
            lab = ent.get("labels", {}).get("en", {}).get("value")
            if lab:
                out[qid] = lab
    return out


def _claim_qid(claims: dict, prop: str) -> str | None:
    try:
        return claims[prop][0]["mainsnak"]["datavalue"]["value"]["id"]
    except (KeyError, IndexError, TypeError):
        return None


def _claim_qids(claims: dict, prop: str) -> list[str]:
    out = []
    for c in claims.get(prop, []):
        try:
            out.append(c["mainsnak"]["datavalue"]["value"]["id"])
        except (KeyError, TypeError):
            continue
    return out


def _claim_amount(claims: dict, prop: str) -> tuple[float | None, str | None, str | None]:
    try:
        dv = claims[prop][0]["mainsnak"]["datavalue"]["value"]
        amount = float(dv["amount"])
        unit = dv.get("unit", "")
        year = None
        quals = claims[prop][0].get("qualifiers", {})
        if "P585" in quals:  # point in time
            year = quals["P585"][0]["datavalue"]["value"]["time"][1:5]
        return amount, unit, year
    except (KeyError, IndexError, TypeError, ValueError):
        return None, None, None


def _claim_quantity(claims: dict, prop: str) -> int | None:
    try:
        return int(float(claims[prop][0]["mainsnak"]["datavalue"]["value"]["amount"]))
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _claim_year(claims: dict, prop: str) -> int | None:
    try:
        t = claims[prop][0]["mainsnak"]["datavalue"]["value"]["time"]
        return int(t[1:5])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


# Rough currency unit (Wikidata uses entity URIs) to EUR conversion. Best effort;
# only used to band revenue for X5/X6, not to publish a figure.
_CCY_TO_EUR = {"Q4916": 0.92, "Q25224": 1.17, "Q180461": 1.0, "Q4917": 0.92}


def _unit_qid(unit_uri: str) -> str:
    return unit_uri.rstrip("/").split("/")[-1] if unit_uri else ""


def _strip_www(host: str) -> str:
    host = host.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _official_site(claims: dict) -> str | None:
    try:
        return _strip_www(urlparse(claims["P856"][0]["mainsnak"]["datavalue"]["value"]).netloc)
    except (KeyError, IndexError, TypeError):
        return None


def resolve(domain: str, name_hint: str | None = None) -> WikidataEntity:
    host = _strip_www(domain)
    base = host.split(".")[0]
    candidates: list[str] = []
    try:
        for q in {name_hint or base, base}:
            data = _get({"action": "wbsearchentities", "search": q,
                         "language": "en", "format": "json", "type": "item",
                         "limit": 7})
            candidates += [x["id"] for x in data.get("search", [])]
    except Exception:
        return WikidataEntity()

    seen, ordered = set(), []
    for q in candidates:
        if q not in seen:
            seen.add(q); ordered.append(q)
    if not ordered:
        return WikidataEntity()

    try:
        data = _get({"action": "wbgetentities", "ids": "|".join(ordered[:8]),
                     "props": "claims|labels", "format": "json"})
    except Exception:
        return WikidataEntity()

    entities = data.get("entities", {})
    chosen_qid = None
    chosen_by = ""
    # 1) exact website host match
    for qid in ordered:
        if _official_site(entities.get(qid, {}).get("claims", {})) == host:
            chosen_qid, chosen_by = qid, "website"
            break
    # 2) first candidate that is an organisation — but never one whose official
    # website is a different domain: a shared name is not the same company
    # (etex.com, a Saudi textile firm, is not Etex at etexgroup.com).
    if not chosen_qid:
        for qid in ordered:
            claims = entities.get(qid, {}).get("claims", {})
            site = _official_site(claims)
            if site and site != host:
                continue
            if set(_claim_qids(claims, "P31")) & _ORG_QIDS:
                chosen_qid, chosen_by = qid, "organisation"
                break
    if not chosen_qid:
        return WikidataEntity()

    ent = entities[chosen_qid]
    claims = ent.get("claims", {})
    label = ent.get("labels", {}).get("en", {}).get("value")

    country_qid = _claim_qid(claims, "P17")
    industry_qid = _claim_qid(claims, "P452")
    parent_qid = _claim_qid(claims, "P749")
    sub_qids = _claim_qids(claims, "P355")
    need = [q for q in [country_qid, industry_qid, parent_qid, *sub_qids] if q]
    labels = _labels(need)

    # India subsidiary detection: any subsidiary located in India.
    india_sub = False
    if sub_qids:
        try:
            subdata = _get({"action": "wbgetentities", "ids": "|".join(sub_qids[:40]),
                            "props": "claims|labels", "format": "json"})
            for sq, se in subdata.get("entities", {}).items():
                sc = se.get("claims", {})
                if _INDIA_QID in _claim_qids(sc, "P17"):
                    india_sub = True
                    break
                slab = se.get("labels", {}).get("en", {}).get("value", "").lower()
                if "india" in slab:
                    india_sub = True
                    break
        except Exception:
            pass

    revenue_eur = None
    amount, unit_uri, rev_year = _claim_amount(claims, "P2139")
    if amount is not None:
        rate = _CCY_TO_EUR.get(_unit_qid(unit_uri or ""), 1.0)
        revenue_eur = int(amount * rate)

    try:
        site = claims["P856"][0]["mainsnak"]["datavalue"]["value"]
    except (KeyError, IndexError, TypeError):
        site = None

    return WikidataEntity(
        found=True, qid=chosen_qid, label=label, website=site,
        country=labels.get(country_qid or ""),
        industry=labels.get(industry_qid or ""),
        inception_year=_claim_year(claims, "P571"),
        employees=_claim_quantity(claims, "P1128"),
        revenue_eur=revenue_eur, revenue_year=rev_year,
        parent=labels.get(parent_qid or ""),
        subsidiaries=[labels.get(q, q) for q in sub_qids][:30],
        india_subsidiary=india_sub, matched_by=chosen_by,
    )
