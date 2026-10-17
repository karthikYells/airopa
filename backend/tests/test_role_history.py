"""Roles they cannot fill: only claimed after watching the site long enough,
and only for roles still listed."""
from __future__ import annotations

from datetime import date

from app.data.records import CompanyRecord
from app.signals import role_history

D = "example.nl"
URL = "https://example.nl/careers"


def test_first_visit_claims_nothing():
    doc = role_history.observe(D, ["Data Engineer", "SAP Consultant"], URL, today=date(2026, 6, 1))
    assert role_history.open_days(doc, today=date(2026, 6, 1)) is None
    rec = CompanyRecord(input_url=D)
    assert not role_history.apply_open_days(rec, doc, URL, today=date(2026, 6, 1))
    assert rec.get("HIRE.06") is None


def test_roles_still_listed_accumulate_days():
    role_history.observe(D, ["Data Engineer", "SAP Consultant", "Controller"], URL, today=date(2026, 6, 1))
    # Controller filled; a new role appears; titles differ only in spacing/case.
    role_history.observe(D, ["data  engineer", "SAP Consultant", "Product Owner"], URL, today=date(2026, 8, 1))
    doc = role_history.observe(D, ["Data Engineer", "SAP Consultant", "Product Owner"], URL,
                               today=date(2026, 9, 15))
    assert set(doc["first_seen"]) == {"data engineer", "sap consultant", "product owner"}
    med, long_open = role_history.open_days(doc, today=date(2026, 9, 15))
    assert med == 106 and long_open == 2   # 106, 106, 45 days

    rec = CompanyRecord(input_url=D)
    assert role_history.apply_open_days(rec, doc, URL, today=date(2026, 9, 15))
    ev = rec.get("HIRE.06")
    assert ev.value == 106 and ev.as_of_date == "2026-09-15" and "2 of 3" in ev.notes


def test_failed_crawl_does_not_reset_history():
    role_history.observe(D, ["Data Engineer"], URL, today=date(2026, 6, 1))
    doc = role_history.observe(D, [], URL, today=date(2026, 9, 1))
    assert doc["first_seen"] == {"data engineer": "2026-06-01"}


def test_recheck_task_needs_the_key(monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    client = TestClient(app)
    monkeypatch.setattr(get_settings(), "task_key", "")
    assert client.post("/api/tasks/recheck-roles").status_code == 404   # off when unset
    monkeypatch.setattr(get_settings(), "task_key", "s3cret-test-key")
    assert client.post("/api/tasks/recheck-roles", headers={"X-Task-Key": "wrong"}).status_code == 404
    r = client.post("/api/tasks/recheck-roles", headers={"X-Task-Key": "s3cret-test-key"})
    assert r.status_code == 200 and r.json() == {"due": 0, "checked": []}
