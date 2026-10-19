"""Tariffs from the World Bank's WITS (UNCTAD TRAINS) database — free, no key.

The EU's standard (MFN) tariff on a six-digit product, as WITS publishes it
for the European Union (reporter 918). WITS answers slowly (~35 s), so each
product's rate is cached in the shared store for 180 days and a failed or
slow call returns None (the dimension then says "not resolved").
"""
from __future__ import annotations

import time

import httpx

from app.data import kv

_URL = "https://wits.worldbank.org/API/V1/SDMX/V21/datasource/TRN/reporter/{rep}/partner/000/product/{hs}/year/{year}/datatype/reported?format=JSON"
_TTL = 180 * 86400
EU = "918"


def parse_rate(d: dict) -> float | None:
    """The simple-average tariff (first observation value) from a WITS answer."""
    try:
        series = d["dataSets"][0]["series"]
        obs = next(iter(series.values()))["observations"]
        v = next(iter(obs.values()))[0]
        return float(v) if v is not None else None
    except Exception:
        return None


def mfn_tariff(hs6: str, reporter: str = EU, years=("2024", "2023", "2022"),
               timeout: float = 60.0) -> dict | None:
    """{"rate": percent, "year": "2023", "hs": hs6} or None."""
    hs6 = "".join(ch for ch in hs6 if ch.isdigit())[:6]
    if len(hs6) != 6:
        return None
    key = f"{reporter}-{hs6}"
    doc = kv.get("wits", key)
    if doc and time.time() - doc.get("fetched_at", 0) < _TTL:
        return doc.get("result")
    result = None
    for year in years:
        try:
            r = httpx.get(_URL.format(rep=reporter, hs=hs6, year=year), timeout=timeout)
            if r.status_code != 200:
                continue
            rate = parse_rate(r.json())
            if rate is not None:
                result = {"rate": rate, "year": year, "hs": hs6,
                          "source_url": _URL.format(rep=reporter, hs=hs6, year=year)}
                break
        except Exception:
            break   # slow or down: do not try older years now
    if result is not None:
        kv.put("wits", key, {"result": result, "fetched_at": time.time()})
    return result
