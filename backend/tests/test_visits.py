"""Visit log and the private dashboard."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.api import visits
from app.config import get_settings
from app.data import kv
from app.main import app


def _wait_enriched():
    for _ in range(50):
        rows = visits.recent()
        if rows and all(r.get("network_owner") for r in rows):
            return rows
        time.sleep(0.05)
    return visits.recent()


def test_a_check_is_logged_with_network_but_ip_shortened(monkeypatch):
    monkeypatch.setattr(get_settings(), "visit_full_ip", False)
    c = TestClient(app)
    c.post("/api/europe/score", json={"url": "not a domain"}, headers={"x-forwarded-for": "203.0.113.45"})
    c.post("/api/score", json={"url": "nordwind-praezision.de"}, headers={"x-forwarded-for": "203.0.113.45",
                                                                         "referer": "https://accessindia.nl/engines/"})
    rows = _wait_enriched()
    r = next(x for x in rows if x["company_checked"] == "nordwind-praezision.de")
    assert r["engine"] == "india" and r["event"] == "check" and r["ip"] is None
    assert r["ip_prefix"] == "203.0.113.0/24" and r["network_owner"] == "Test Network BV" and r["country"] == "NL"
    assert r["referer"] == "https://accessindia.nl/engines/" and len(r["visitor"]) == 16


def test_full_ip_only_when_switched_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "visit_full_ip", True)
    TestClient(app).post("/api/score", json={"url": "nordwind-praezision.de"}, headers={"x-forwarded-for": "198.51.100.7"})
    assert any(r.get("ip") == "198.51.100.7" for r in _wait_enriched())


def test_dashboard_is_hidden_without_the_key(monkeypatch):
    c = TestClient(app)
    monkeypatch.setattr(get_settings(), "dashboard_key", "")
    assert c.get("/api/internal/visits").status_code == 404
    monkeypatch.setattr(get_settings(), "dashboard_key", "k-123456")
    assert c.get("/api/internal/visits?key=wrong").status_code == 404
    c.post("/api/score", json={"url": "nordwind-praezision.de"}, headers={"x-forwarded-for": "192.0.2.9"})
    _wait_enriched()
    r = c.get("/api/internal/visits?key=k-123456")
    assert r.status_code == 200 and "nordwind-praezision.de" in r.text and "Test Network BV" in r.text


def test_old_visits_are_pruned(monkeypatch):
    kv.put(visits.COLLECTION, "20200101T000000-aaaaaa", {"at": "2020-01-01T00:00:00+00:00", "ts": 1577836800})
    kv.put(visits.COLLECTION, "29990101T000000-bbbbbb", {"at": "2999-01-01T00:00:00+00:00", "ts": time.time()})
    assert visits.prune() == 1 and kv.get(visits.COLLECTION, "29990101T000000-bbbbbb")
