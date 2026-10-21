"""Run retention (Section 9.6 traceability, Section 7 reproducibility).

Every run is retained in full so any page can be reconstructed and defended.
SQLite by default; set DATABASE_URL to a Postgres URL in production with no code
change. This is deliberately minimal in v1 — the peer and India reference stores
(Section 6) are the assets to invest in next and get their own tables here later.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import JSON, Column, DateTime, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

Base = declarative_base()


class Run(Base):
    __tablename__ = "runs"
    id = Column(String, primary_key=True)
    host = Column(String, index=True)
    surface = Column(String)
    mode = Column(String, nullable=True)
    config_version = Column(String)
    created_at = Column(DateTime)
    payload = Column(Text)  # full public payload or internal brief, as JSON


_engine = None
_Session = None


def init_db() -> None:
    global _engine, _Session
    settings = get_settings()
    url = settings.database_url
    if url.startswith("sqlite"):
        import os
        os.makedirs("data", exist_ok=True)
    _engine = create_engine(url, future=True)
    Base.metadata.create_all(_engine)
    _Session = sessionmaker(bind=_engine, future=True)


def save_run(host: str, surface: str, mode: str | None, payload: dict) -> str:
    if _Session is None:
        init_db()
    run_id = uuid.uuid4().hex
    with _Session() as s:
        s.add(Run(
            id=run_id, host=host, surface=surface, mode=mode,
            config_version=get_settings().config_version,
            created_at=datetime.now(timezone.utc),
            payload=json.dumps(payload, default=str),
        ))
        s.commit()
    return run_id


def get_run(run_id: str) -> dict | None:
    """A stored run: what exactly was shown, so a report matches the page."""
    if _Session is None:
        init_db()
    with _Session() as s:
        r = s.get(Run, run_id)
        if r is None:
            return None
        return {"id": r.id, "host": r.host, "surface": r.surface, "mode": r.mode,
                "created_at": r.created_at, "payload": json.loads(r.payload)}


def latest_public_run(host: str, max_age_hours: float, surface: str = "public") -> dict | None:
    """Most recent public snapshot for a domain, if fresh enough to reuse
    (Section 9.7: repeated lookups of the same company cost nothing)."""
    if _Session is None:
        init_db()
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=max_age_hours)
    with _Session() as s:
        r = (s.query(Run).filter(Run.host == host, Run.surface == surface,
                                 Run.created_at >= cutoff)
             .order_by(Run.created_at.desc()).first())
        if r is None:
            return None
        return {"id": r.id, "payload": json.loads(r.payload)}


class Lead(Base):
    """A report request from the public page (Section 9.5 lead capture)."""
    __tablename__ = "leads"
    id = Column(String, primary_key=True)
    created_at = Column(DateTime)
    run_id = Column(String, index=True)
    host = Column(String, index=True)
    name = Column(String)
    email = Column(String, index=True)
    email_type = Column(String)        # work | personal
    company = Column(String)
    role = Column(String, nullable=True)
    call_partner = Column(String)      # yes | no
    status = Column(String)            # sent | queued | failed
    detail = Column(Text, nullable=True)


def save_lead(engine: str | None = None, **fields) -> str:
    if _Session is None:
        init_db()
    lead_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    with _Session() as s:
        s.add(Lead(id=lead_id, created_at=now, **fields))
        s.commit()
    # The server's own database is wiped on every deploy; Firestore keeps the
    # lead. Doc id starts with the time so the dashboard can list newest first.
    from app.data import kv
    kv.put("leads", f"{now.strftime('%Y%m%dT%H%M%S')}-{lead_id[:8]}",
           {"at": now.isoformat(timespec="seconds"), "ts": now.timestamp(), "id": lead_id, "engine": engine, **fields})
    return lead_id


def recent_leads(limit: int = 200) -> list[dict]:
    from app.data import kv
    ids = sorted(kv.keys("leads", limit=5000), reverse=True)[:limit]
    return [d for d in (kv.get("leads", i) for i in ids) if d]


_LEAD_RETENTION_DAYS = 730      # privacy notice: "kept for up to 24 months", then deleted


def prune_leads() -> int:
    import time
    from app.data import kv
    cutoff, gone = time.time() - _LEAD_RETENTION_DAYS * 86400, 0
    for i in kv.keys("leads", limit=20000):
        d = kv.get("leads", i)
        if d and d.get("ts", 0) < cutoff:
            kv.delete("leads", i)
            gone += 1
    return gone
