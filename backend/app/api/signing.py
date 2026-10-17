"""Signed snapshot tokens, so a report can be built from exactly what the
visitor saw even if the server restarted in between (Cloud Run keeps no files).

The page receives the token with the snapshot and sends it back with the report
request. The HMAC proves the engine produced it, so a visitor cannot alter what
goes into their PDF. SNAPSHOT_SIGNING_KEY must be the same on every instance.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets

from app.config import get_settings

_FALLBACK_KEY = secrets.token_hex(32)  # per process; set SNAPSHOT_SIGNING_KEY in production


def _key() -> bytes:
    return (get_settings().snapshot_signing_key or _FALLBACK_KEY).encode()


def sign(run_id: str, host: str, payload: dict) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps({"id": run_id, "host": host, "payload": payload},
                   separators=(",", ":"), default=str).encode()).decode()
    mac = hmac.new(_key(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def verify(token: str) -> dict | None:
    """The signed {id, host, payload}, or None if the token is missing or altered."""
    try:
        body, mac = token.rsplit(".", 1)
        good = hmac.new(_key(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, good):
            return None
        return json.loads(base64.urlsafe_b64decode(body.encode()))
    except Exception:
        return None
