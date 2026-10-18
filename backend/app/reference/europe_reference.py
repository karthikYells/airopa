"""Europe reference data v1 (Europe Market Assessment, Phase 4).

Loaded from europe/europe_reference_v1.json: goods demand per HS group
(Eurostat 2025), services demand (Eurostat 2024), regulatory rules with their
official sources, and the ranked target countries. Like the India reference,
every value is a lookup and is the same for every company in a sector. Rules
flagged `verify` are not quoted on the public page until re-checked.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).resolve().parent / "europe" / "europe_reference_v1.json"

# HS chapter (or 4-digit heading) -> v1 goods group id. 8708 is checked first.
_HS_GROUP = {"8708": "eng_auto", "72": "eng_steel", "73": "eng_steelart", "84": "eng_mach",
             "28": "chem_inorg", "29": "chem_org", "30": "chem_pharma", "32": "chem_dyes",
             "38": "chem_misc", "61": "tex_apparel", "62": "tex_apparel", "63": "tex_madeups",
             "41": "tex_leather", "42": "tex_leather", "64": "tex_footwear",
             **{str(c): "tex_fabric" for c in range(50, 61)}}

# v1 sectors, as the rules name them.
SECTORS = {
    "engineering_auto": "Engineering and auto components",
    "chemicals_pharma": "Chemicals and pharma",
    "textiles_apparel_leather": "Textiles, apparel and leather",
    "it_services": "IT, engineering and business services",
}


@lru_cache(maxsize=1)
def data() -> dict:
    return json.loads(_PATH.read_text(encoding="utf-8"))


def version() -> str:
    return data()["meta"]["version"]


def group_for_hs(hs: str) -> dict | None:
    """The v1 goods group a product code falls in, or None if outside v1."""
    hs = "".join(ch for ch in str(hs) if ch.isdigit())
    gid = _HS_GROUP.get(hs[:4]) or _HS_GROUP.get(hs[:2])
    return next((g for g in data()["goods"] if g["id"] == gid), None) if gid else None


def sector_for_hs(hs: str) -> str | None:
    g = group_for_hs(hs)
    return g["sector"] if g else None


def services(code: str | None = None) -> list[dict]:
    rows = data()["services"]
    return [r for r in rows if r["code"] == code] if code else rows


def rules_for(sector: str, public_only: bool = True) -> list[dict]:
    """Rules for a v1 sector (plus the all-sector trade rules). With
    `public_only`, rules still flagged `verify` are left out."""
    label = SECTORS.get(sector, sector)
    rows = [r for r in data()["rules"] if r["sector"] == label or r["sector"].startswith("All sectors")]
    return [r for r in rows if not (public_only and r.get("verify"))]


def target_countries() -> list[str]:
    return list(data()["meta"]["top_countries"])
