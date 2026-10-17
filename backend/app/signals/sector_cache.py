"""Remembers each company's sector so repeat runs give the same answer.

The sector keys the India reference lookup, so it drives both public scores.
A model can pick a different (equally defensible) sector on a second run —
Picnic came back once as consumer goods, once as logistics — which would move
a prospect's scores between visits. The first model-decided sector per domain
is stored (app.data.kv) and reused. Delete the entry to re-classify.
"""
from __future__ import annotations

from app.data import kv

_COLLECTION = "sectors"


def get(domain: str) -> str | None:
    doc = kv.get(_COLLECTION, domain)
    return doc.get("sector") if doc else None


def put(domain: str, sector_key: str) -> None:
    kv.put(_COLLECTION, domain, {"sector": sector_key})
