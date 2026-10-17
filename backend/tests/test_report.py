"""Email-report flow (Section 9.5), offline: no mail provider, no network."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import ratelimit

from app.api.email_check import check_email
from app.data.store import save_run
from app.main import app
from app.reports.pdf import build_pdf

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """Each test is a fresh visitor; the limiter itself is exercised separately."""
    ratelimit._hits.clear()
    yield

PAYLOAD = {
    "mode": "STANDARD",
    "company": {"input": "example.de", "name": "Example GmbH", "sector": "Industrial machinery",
                "country": "Germany", "revenue": "EUR 640m", "headcount": "2,300 people"},
    "india_status": "Public sources show no India entity and no India technology presence today.",
    "own_evidence": [{"title": "You are hiring now", "tone": "blue",
                      "bullets": ["**34 open roles** on your careers site today."],
                      "as_of": "2026-10-17"}],
    "withheld": ["A costed team model against your own salary bands"],
    "lead_capture": {"type": "business_case", "field": "work_email",
                     "title": "Get the full business case in two weeks", "offer": "No obligation."},
    "disclaimer": "Indicative and compiled from public sources.",
}


def _run_id() -> str:
    return save_run("example.de", "public", "STANDARD", PAYLOAD)


def _body(**over):
    body = {"run_id": _run_id(), "name": "Anna de Vries", "email": "anna@example.de",
            "company": "Example GmbH", "role": "CFO / Finance"}
    body.update(over)
    return body


def test_pdf_is_a_real_pdf_without_gcc_fit():
    pdf = build_pdf(PAYLOAD, recipient_name="Anna")
    assert pdf.startswith(b"%PDF") and len(pdf) > 2000
    assert b"GCC Fit" not in pdf


def test_work_email_is_queued_when_no_mail_provider():
    r = client.post("/api/report", json=_body())
    assert r.status_code == 200 and r.json()["status"] == "queued"


def test_personal_email_needs_explicit_allow():
    r = client.post("/api/report", json=_body(email="anna@gmail.com"))
    assert r.status_code == 422 and r.json()["detail"] == "personal_email"
    r = client.post("/api/report", json=_body(email="anna@gmail.com", allow_personal=True))
    assert r.status_code == 200 and r.json()["status"] == "queued"


def test_honeypot_and_bad_inputs():
    assert client.post("/api/report", json=_body(bot_field="x")).json()["status"] == "sent"
    assert client.post("/api/report", json=_body(email="not-an-email")).status_code == 422
    assert client.post("/api/report", json=_body(run_id="nope")).status_code == 404


def test_email_check_matches_business_case_engine():
    assert check_email("Anna@Example.DE") == {"ok": True, "email": "anna@example.de", "personal": False}
    assert check_email("x@ziggo.nl")["personal"] is True
    assert check_email("bad@")["ok"] is False


def test_internal_view_can_be_switched_off(monkeypatch):
    from app.api import routes_internal
    from app.config import Settings
    monkeypatch.setattr(routes_internal, "get_settings",
                        lambda: Settings(enable_internal=False, _env_file=None))
    assert client.post("/api/assess", json={"url": "example.de"}).status_code == 404


def test_email_is_branded_and_escapes_visitor_input():
    from app.reports.email import build_email
    subject, text, html = build_email(PAYLOAD, "<script>x</script>", "CFO / Finance",
                                      "https://accessindia.nl/engines/india-market-assessment/?company=example.de")
    assert subject == "Your India Market Assessment: Example GmbH"
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "Access India" in html and "GCC Fit" not in html


def test_report_survives_restart_via_signed_snapshot():
    from app.api.signing import sign
    token = sign("gone-after-restart", "example.de", PAYLOAD)
    body = _body(run_id="gone-after-restart", snapshot_token=token)
    assert client.post("/api/report", json=body).json()["status"] == "queued"
    tampered = token[:-4] + ("0000" if not token.endswith("0000") else "1111")
    assert client.post("/api/report", json={**body, "snapshot_token": tampered}).status_code == 404


def test_report_rate_limit_per_visitor():
    for _ in range(5):
        client.post("/api/report", json=_body())
    assert client.post("/api/report", json=_body()).status_code == 429
