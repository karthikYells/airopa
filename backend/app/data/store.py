"""Run retention (Section 9.6 traceability, Section 7 reproducibility).

Every run is retained in full so any page can be reconstructed and defended.
SQLite by default; set DATABASE_URL to a Postgres URL in production with no code
change. This is deliberately minimal in v1 — the peer and India reference stores
(Section 6) are the assets to invest in next and get their own tables here later.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

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
