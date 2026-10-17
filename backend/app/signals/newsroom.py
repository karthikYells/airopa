"""Dated pressure from the company's own newsroom (Section 5.5, PRESS).

The model only extracts; this module decides. An event is kept only if its
headline appears verbatim on the page it came from and its date is real, in
the past, and within 36 months (older events score zero anyway). Each kept
type becomes one PRESS signal carrying the event date and the page URL, so the
freshness decay of Section 5.5 applies and every claim traces to a source.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from app.data.evidence import Evidence, Method, SourceAuthority, SourceType

# Event type -> PRESS signal. 'results' and 'other' carry no pressure on their
# own (a margin claim needs the figures: annual report extraction).
TYPE_TO_SIGNAL = {
    "cost_programme": "PRESS.03",
    "restructuring": "PRESS.04",
    "erp_migration": "PRESS.05",
    "acquisition": "PRESS.09",
    "leadership_change": "PRESS.11",
    "facility_change": "PRESS.18",
}

_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", (s or "")).strip().casefold()


def _parse_date(s: str) -> date | None:
    s = (s or "").strip()
    for fmt, size in (("%Y-%m-%d", 10), ("%Y-%m", 7)):
        try:
            return datetime.strptime(s[:size], fmt).date()
        except ValueError:
            continue
    return None


def verify_events(events: list[dict], pages: list[dict], today: date | None = None) -> list[dict]:
    """Keep only events whose headline is on its page and whose date is plausible."""
    today = today or date.today()
    texts = {p["url"]: _norm(p["text"]) for p in pages}
    kept = []
    for e in events:
        head, url = (e.get("headline") or "").strip(), e.get("url") or ""
        d = _parse_date(e.get("date", ""))
        if not head or len(head) < 12 or d is None:
            continue
        if d > today or (today - d).days > 36 * 30.5:
            continue
        page_text = texts.get(url) or next((t for t in texts.values() if _norm(head) in t), "")
        if _norm(head) not in page_text:
            continue  # not on the page: the model's words, not theirs — dropped
        if url not in texts:
            url = next(u for u, t in texts.items() if _norm(head) in t)
        kept.append({"headline": head, "date": d.isoformat(), "url": url,
                     "type": e.get("type") if e.get("type") in TYPE_TO_SIGNAL
                     or e.get("type") in ("results", "india_expansion") else "other"})
    return sorted(kept, key=lambda x: x["date"], reverse=True)


def apply_events(rec, events: list[dict]) -> int:
    """Most recent verified event per PRESS signal becomes evidence. Returns count."""
    added = 0
    for etype, sid in TYPE_TO_SIGNAL.items():
        e = next((x for x in events if x["type"] == etype), None)
        if e is None:
            continue
        rec.add(Evidence(sid, True, source_url=e["url"], source_type=SourceType.COMPANY_SITE,
                         source_authority=SourceAuthority.PRIMARY, method=Method.MODEL,
                         as_of_date=e["date"], confidence=0.6,
                         notes=f"Newsroom: \"{e['headline']}\" ({e['date']})"))
        added += 1
    return added
