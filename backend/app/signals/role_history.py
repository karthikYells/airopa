"""Roles they cannot fill (HIRE.06), observed over time on their own careers site.

Each visit records the roles listed and the date each was first seen. A role
that disappears is treated as filled or closed and dropped. HIRE.06 is the
median number of days the currently listed roles have been open since first
seen — a lower bound, never an estimate. It only resolves once we have watched
the site for at least `_MIN_SPAN_DAYS`, so a first visit never claims anything.
"""
from __future__ import annotations

import re
from datetime import date
from statistics import median

from app.data import kv
from app.data.evidence import Evidence, Method, SourceAuthority, SourceType

_COLLECTION = "roles"
_MIN_SPAN_DAYS = 30


def _norm(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().lower()


def observe(domain: str, titles: list[str], careers_url: str | None = None,
            today: date | None = None) -> dict:
    """Record today's listing and return the stored history document."""
    today = today or date.today()
    doc = kv.get(_COLLECTION, domain) or {}
    seen: dict = doc.get("first_seen", {})
    current = {_norm(t): t for t in titles if t and t.strip()}
    if current:  # an empty or failed crawl is not evidence that roles were filled
        seen = {k: seen.get(k, today.isoformat()) for k in current}
    doc = {"domain": domain, "first_seen": seen,
           "first_observed": doc.get("first_observed", today.isoformat()),
           "last_checked": today.isoformat(),
           "careers_url": careers_url or doc.get("careers_url"),
           "observations": int(doc.get("observations", 0)) + 1}
    kv.put(_COLLECTION, domain, doc)
    return doc


def open_days(doc: dict, today: date | None = None) -> tuple[int, int] | None:
    """(median days open, roles open 90+ days), or None while too little history."""
    today = today or date.today()
    try:
        span = (today - date.fromisoformat(doc["first_observed"])).days
    except Exception:
        return None
    seen = doc.get("first_seen") or {}
    if span < _MIN_SPAN_DAYS or not seen:
        return None
    days = [(today - date.fromisoformat(d)).days for d in seen.values()]
    return int(median(days)), sum(1 for d in days if d >= 90)


def apply_open_days(rec, doc: dict, source_url: str, today: date | None = None) -> bool:
    got = open_days(doc, today)
    if got is None:
        return False
    med, long_open = got
    rec.add(Evidence("HIRE.06", med, unit="days open", source_url=source_url,
                     source_type=SourceType.COMPANY_SITE, source_authority=SourceAuthority.PRIMARY,
                     confidence=0.6, method=Method.PARSER, as_of_date=doc["last_checked"],
                     notes=f"{long_open} of {len(doc['first_seen'])} listed roles open 90+ days; "
                           f"site watched since {doc['first_observed']}"))
    return True
