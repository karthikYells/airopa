"""Small persistent key-value store: one JSON document per (collection, key).

Cloud Run's disk is wiped on every restart, so anything that must outlive an
instance (role first-seen dates, saved sectors, the Apollo cache) goes here.
`store_backend = "firestore"` uses Firestore in the same Google Cloud project
(free tier; credentials come from the Cloud Run service account). Anything
else uses local files under data/kv/. Never raises: a failed read is a miss,
a failed write is dropped.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.config import get_settings

_DIR = Path(__file__).resolve().parents[2] / "data" / "kv"
_client = None


def _safe(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", key)[:300]


def _firestore():
    global _client
    if _client is None:
        from google.cloud import firestore
        _client = firestore.Client()
    return _client


def _use_firestore() -> bool:
    return get_settings().store_backend == "firestore"


def get(collection: str, key: str) -> dict | None:
    try:
        if _use_firestore():
            snap = _firestore().collection(collection).document(_safe(key)).get()
            return snap.to_dict() if snap.exists else None
        path = _DIR / collection / f"{_safe(key)}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except Exception:
        return None


def put(collection: str, key: str, doc: dict) -> None:
    try:
        if _use_firestore():
            _firestore().collection(collection).document(_safe(key)).set(doc)
            return
        path = _DIR / collection / f"{_safe(key)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    except Exception:
        pass


def keys(collection: str, limit: int = 500) -> list[str]:
    try:
        if _use_firestore():
            return [d.id for d in _firestore().collection(collection).limit(limit).stream()]
        folder = _DIR / collection
        return sorted(p.stem for p in folder.glob("*.json"))[:limit] if folder.exists() else []
    except Exception:
        return []


def delete(collection: str, key: str) -> None:
    try:
        if _use_firestore():
            _firestore().collection(collection).document(_safe(key)).delete()
            return
        (_DIR / collection / f"{_safe(key)}.json").unlink(missing_ok=True)
    except Exception:
        pass
