"""Eurostat trade data — free, no key, product level (Europe Market Assessment).

Goods: Comext DS-045409, imports by HS code, reporter country and partner
(India, China, all non-EU countries), annual values in EUR. Services:
bop_its6_det, EU imports by service type. Returns only what Eurostat
publishes; a missing cell stays missing (never filled). Results are cached
in the shared store for 30 days, so a product is fetched once per month.
"""
from __future__ import annotations

import hashlib
import json
import time

import httpx

from app.data import kv

_COMEXT = "https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/DS-045409"
_BOP = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/bop_its6_det"
_TIMEOUT = httpx.Timeout(90.0, connect=10.0)
_TTL = 30 * 86400
EXTRA_EU = "EXT_EU"          # Comext partner code for all non-EU countries


def parse_jsonstat(d: dict) -> list[dict]:
    """JSON-stat 2.0 dataset -> one dict per published cell: every dimension
    code plus `value`. Cells Eurostat does not publish are not returned."""
    ids, sizes, dims = d["id"], d["size"], d["dimension"]
    rev = {k: {i: code for code, i in dims[k]["category"]["index"].items()} for k in ids}
    strides, acc = [], 1
    for s in reversed(sizes):
        strides.insert(0, acc)
        acc *= s
    out = []
    for flat, value in (d.get("value") or {}).items():
        flat = int(flat)
        cell = {k: rev[k][(flat // st) % sz] for k, st, sz in zip(ids, strides, sizes)}
        cell["value"] = value
        out.append(cell)
    return out


def _cached(url: str, params: list[tuple]) -> dict | None:
    key = hashlib.sha256(json.dumps([url, sorted(params)]).encode()).hexdigest()[:40]
    doc = kv.get("eurostat", key)
    if doc and time.time() - doc.get("fetched_at", 0) < _TTL:
        return doc["data"]
    try:
        r = httpx.get(url, params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None
    if "value" not in data:
        return None
    kv.put("eurostat", key, {"data": data, "fetched_at": time.time(), "url": url})
    return data


def goods_imports(products: list[str], reporters: list[str], partners: list[str],
                  years: list[str]) -> list[dict]:
    """Annual import values (EUR) for HS codes (2, 4, 6 or 8 digits) into the
    given reporters ("EU" or an EU country code) from the given partners."""
    out = []
    for prod in products:
        params = [("format", "JSON"), ("freq", "A"), ("product", prod), ("flow", "1"),
                  ("indicators", "VALUE_IN_EUROS")]
        params += [("reporter", r) for r in reporters] + [("partner", p) for p in partners]
        params += [("time", y) for y in years]
        data = _cached(_COMEXT, params)
        if data:
            out += parse_jsonstat(data)
    return out


def services_imports(items: list[str], partners: list[str], years: list[str],
                     geo: str = "EU27_2020") -> list[dict]:
    """EU imports of services (EUR million) by BPM6 item, e.g. SI (computer and
    telecoms) or SJ (other business services)."""
    params = [("format", "JSON"), ("lang", "EN"), ("geo", geo), ("stk_flow", "DEB"),
              ("currency", "MIO_EUR")]
    params += [("bop_item", i) for i in items] + [("partner", p) for p in partners]
    params += [("time", y) for y in years]
    data = _cached(_BOP, params)
    return parse_jsonstat(data) if data else []


# Below this, a six-digit market is too narrow to speak for demand; use the heading.
NARROW_MARKET_EUR = 50_000_000


def demand_view(hs: str, reporters: tuple[str, ...] = ("EU",)) -> dict | None:
    """market_view for the product's own code, stepping up to its four-digit
    heading when the six-digit market is under EUR 50m. `basis` says which."""
    v = market_view(hs, reporters=reporters)
    if len(hs) > 4 and (v is None or v["extra_eu"] < NARROW_MARKET_EUR):
        h = market_view(hs[:4], reporters=reporters)
        if h is not None:
            return {**h, "basis": "heading", "product_hs": hs, "product_view": v}
    return {**v, "basis": "product"} if v else None


def market_view(hs: str, years: tuple[str, str] = ("2023", "2025"),
                reporters: tuple[str, ...] = ("EU",)) -> dict | None:
    """Europe's demand for one HS code and India's position in it: imports from
    all non-EU countries, from India and from China, growth per year, shares.
    None if Eurostat has nothing for the code."""
    first, last = years
    cells = goods_imports([hs], list(reporters), ["IN", "CN", EXTRA_EU], [first, last])
    get = {(c["reporter"], c["partner"], c["time"]): c["value"] for c in cells}
    rep = reporters[0]
    ext_l, ext_f = get.get((rep, EXTRA_EU, last)), get.get((rep, EXTRA_EU, first))
    if not ext_l:
        return None
    in_l, in_f = get.get((rep, "IN", last)), get.get((rep, "IN", first))
    cn_l = get.get((rep, "CN", last))
    span = int(last) - int(first)

    def cagr(a, b):
        return (a / b) ** (1 / span) - 1 if a and b and span > 0 else None
    return {
        "hs": hs, "reporter": rep, "year": last,
        "extra_eu": ext_l, "extra_eu_growth": cagr(ext_l, ext_f),
        "india": in_l, "india_growth": cagr(in_l, in_f),
        "india_share": (in_l / ext_l) if in_l is not None else None,
        "china_share": (cn_l / ext_l) if cn_l is not None else None,
        "source_url": f"{_COMEXT}?product={hs}&reporter={rep}&flow=1",
    }
