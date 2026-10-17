"""Per-IP rate limiting for the public surface (Section 9.7).

In-memory and per process: enough for one small server. Behind the
accessindia.nl proxy the visitor's address arrives in X-Forwarded-For.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for") or request.headers.get("x-nf-client-connection-ip")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def limit(request: Request, bucket: str, max_hits: int, per_seconds: int) -> None:
    """Raise 429 once an IP exceeds max_hits in the window for this bucket."""
    if max_hits <= 0:
        return
    key = (bucket, client_ip(request))
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > per_seconds:
        q.popleft()
    if len(q) >= max_hits:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    q.append(now)
