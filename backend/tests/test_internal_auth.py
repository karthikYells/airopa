"""The internal surface (GCC Fit) fails closed and needs the shared password.
Every request here is refused before the pipeline runs: no network, no credits."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import routes_internal
from app.config import Settings
from app.main import app

client = TestClient(app)


def _with_token(monkeypatch, token: str) -> None:
    monkeypatch.setattr(routes_internal, "get_settings",
                        lambda: Settings(internal_api_token=token, _env_file=None))


def test_refused_when_no_password_configured(monkeypatch):
    _with_token(monkeypatch, "")
    r = client.post("/api/assess", json={"url": "example.de"},
                    headers={"x-internal-token": "anything"})
    assert r.status_code == 503


def test_missing_or_wrong_password_rejected(monkeypatch):
    _with_token(monkeypatch, "correct-horse-battery-staple")
    assert client.post("/api/assess", json={"url": "example.de"}).status_code == 401
    r = client.post("/api/assess", json={"url": "example.de"},
                    headers={"x-internal-token": "wrong"})
    assert r.status_code == 401
