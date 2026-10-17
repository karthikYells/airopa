"""Scheduled jobs, called by Cloud Scheduler (not by people).

`POST /api/tasks/recheck-roles` re-reads the careers pages of companies that
have been assessed, so HIRE.06 (roles open 90+ days) builds up between visits.
Protected by the `X-Task-Key` header matching `task_key`; off when unset.
Each call checks a few companies that are due, to stay inside the request
timeout; the scheduler runs it daily. Role history older than a year is deleted.
"""
from __future__ import annotations

import hmac
from datetime import date, timedelta

from fastapi import APIRouter, Header, HTTPException

from app.adapters.web_scraper import scrape
from app.config import get_settings
from app.data import kv
from app.signals import peers, role_history

router = APIRouter()

_RECHECK_EVERY_DAYS = 7
_STOP_AFTER_DAYS = 180   # stop watching a company nobody has looked at again
_PER_CALL = 6
_DELETE_AFTER_DAYS = 365  # role history is deleted a year after we first saw the site


def _authorised(x_task_key: str) -> None:
    key = get_settings().task_key
    if not key or not hmac.compare_digest(x_task_key, key):
        raise HTTPException(status_code=404, detail="not found")


@router.post("/tasks/build-cohorts")
def build_cohorts(x_task_key: str = Header(default="")) -> dict:
    """Builds queued peer sets (Section 5.8); runs every 30 minutes."""
    _authorised(x_task_key)
    from app.adapters.llm import LLM
    settings = get_settings()
    return {"built": peers.build_queued(settings, llm=LLM(settings))}


@router.post("/tasks/recheck-roles")
def recheck_roles(x_task_key: str = Header(default="")) -> dict:
    _authorised(x_task_key)
    today = date.today()
    due = []
    for domain in kv.keys("roles"):
        doc = kv.get("roles", domain) or {}
        try:
            last = date.fromisoformat(doc["last_checked"])
            first = date.fromisoformat(doc["first_observed"])
        except Exception:
            continue
        if today - first > timedelta(days=_DELETE_AFTER_DAYS):
            kv.delete("roles", domain)
            continue
        if today - last >= timedelta(days=_RECHECK_EVERY_DAYS) and \
                today - first <= timedelta(days=_STOP_AFTER_DAYS):
            due.append((last, doc.get("domain") or domain))
    checked = []
    for _, domain in sorted(due)[:_PER_CALL]:
        sr = scrape(domain)
        if sr.reachable and sr.careers_urls:
            role_history.observe(domain, sr.job_titles, careers_url=sr.careers_urls[0], today=today)
            checked.append({"domain": domain, "roles": len(sr.job_titles)})
    return {"due": len(due), "checked": checked}
