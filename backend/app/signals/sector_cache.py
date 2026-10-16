"""Remembers each company's sector so repeat runs give the same answer.

The sector keys the India reference lookup, so it drives both public scores.
A model can pick a different (equally defensible) sector on a second run —
Picnic came back once as consumer goods, once as logistics — which would move
a prospect's scores between visits. The first model-decided sector per domain
is stored and reused. Delete the file (or one entry) to re-classify.
"""
from __future__ import annotations

import json
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "data" / "sector_cache.json"


def _load() -> dict:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get(domain: str) -> str | None:
    return _load().get(domain)


def put(domain: str, sector_key: str) -> None:
    try:
        data = _load()
        data[domain] = sector_key
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    except Exception:
        pass
