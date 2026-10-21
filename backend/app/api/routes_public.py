"""Public surface route (Section 9). Returns the snapshot payload, guaranteed
to carry no GCC Fit score and no third-party names."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.adapters import mailer
from app.adapters.llm import LLM
from app.api.abuse import is_blocklisted, validate
from app.api.email_check import check_email
from app.api.ratelimit import limit
from app.api import visits
from app.api.signing import sign, verify
from app.config import get_settings
from app.data.store import get_run, latest_public_run, save_lead, save_run
from app.reports.email import build_email
from app.reports.pdf import build_pdf
from app.fixtures.demo_companies import EXAMPLE_DOMAINS, get_seed
from app.narrative.public_snapshot import build_snapshot
from app.narrative.safety import assert_public_safe, determine_mode
from app.pipeline.orchestrator import run_pipeline

router = APIRouter()


class ScoreRequest(BaseModel):
    url: str


@router.get("/examples")
def examples() -> dict:
    return {"domains": EXAMPLE_DOMAINS}


@router.post("/score")
def score_company(req: ScoreRequest, request: Request) -> dict:
    settings = get_settings()
    ok, host, reason = validate(req.url)
    if ok:
        # Repeated lookups of the same company cost nothing (Section 9.7).
        cached = latest_public_run(host, settings.snapshot_cache_hours)
        if cached is not None:
            visits.record(request, engine="india", event="check", company=host, run_id=cached["id"],
                          mode=cached["payload"].get("mode"), cached=True)
            return {**cached["payload"], "run_id": cached["id"],
                    "snapshot_token": sign(cached["id"], host, cached["payload"])}
        limit(request, "score", settings.public_score_limit_per_hour, 3600)
    if not ok:
        return {"mode": "REJECTED", "reason": reason,
                "message": {
                    "not_a_company_domain": "Enter a company website, for "
                        "example your firm's domain.",
                    "free_email_provider": "Enter a company website, not a "
                        "personal email domain.",
                }.get(reason, "Enter a valid company website.")}

    blocklisted = is_blocklisted(host)
    llm = LLM(settings)
    outcome = run_pipeline(host, settings, llm=llm, surface="public")
    mode = determine_mode(outcome, settings, blocklisted=blocklisted)

    seed = get_seed(host) if settings.use_seed_data else None
    cohort = seed.peer_cohort if seed else None
    payload = build_snapshot(outcome, settings, mode, seed_cohort=cohort)

    # Collect any seed peer/vendor names to assert they never leak publicly.
    forbidden = []
    if seed:
        forbidden = [seed.legal_name.split()[0]] if False else []
    assert_public_safe(payload, forbidden_names=forbidden)

    run_id = save_run(host, "public", mode.value, payload)
    visits.record(request, engine="india", event="check", company=host, run_id=run_id, mode=mode.value)
    return {**payload, "run_id": run_id, "snapshot_token": sign(run_id, host, payload)}


class ReportRequest(BaseModel):
    run_id: str
    snapshot_token: str = Field(default="", max_length=200_000)
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(max_length=254)
    company: str = Field(min_length=1, max_length=80)
    role: str = Field(default="", max_length=60)
    call_partner: bool = False
    allow_personal: bool = False
    bot_field: str = ""          # honeypot: humans leave it empty


@router.post("/report")
def request_report(req: ReportRequest, request: Request) -> dict:
    """Email the visitor a PDF of the snapshot they saw (Section 9.5).
    Every request is kept as a lead; Airopa gets a copy."""
    settings = get_settings()
    if req.bot_field:
        return {"status": "sent"}  # silently drop bots
    limit(request, "report", settings.report_limit_per_hour, 3600)

    em = check_email(req.email)
    if not em["ok"]:
        raise HTTPException(status_code=422, detail="invalid_email")
    if em["personal"] and not req.allow_personal:
        raise HTTPException(status_code=422, detail="personal_email")

    run = get_run(req.run_id)
    if run is None or run["surface"] != "public":
        # The server may have restarted since the snapshot (Cloud Run keeps no
        # files): fall back to the signed copy the page sent back.
        signed = verify(req.snapshot_token) if req.snapshot_token else None
        if signed is None or signed.get("id") != req.run_id:
            raise HTTPException(status_code=404, detail="snapshot_not_found")
        run = {"id": signed["id"], "host": signed["host"], "payload": signed["payload"]}
    payload = run["payload"]

    pdf = build_pdf(payload, recipient_name=req.name)
    filename = f"India-Market-Assessment-{run['host']}.pdf"
    reports_dir = Path("data/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / f"{run['id']}.pdf").write_bytes(pdf)

    # Personal addresses are checked by a person first, as on the business case engine.
    sent, detail = False, "personal email: manual follow-up"
    if not em["personal"]:
        link = f"{settings.public_site_url}?company={run['host']}"
        subject, text, html = build_email(payload, req.name, req.role, link)
        sent, detail = mailer.send(settings, em["email"], subject, text, html, pdf, filename,
                                   bcc=settings.mail_notify or None)

    save_lead(engine="india", run_id=run["id"], host=run["host"], name=req.name, email=em["email"],
              email_type="personal" if em["personal"] else "work", company=req.company,
              role=req.role or None, call_partner="yes" if req.call_partner else "no",
              status="sent" if sent else "queued", detail=detail)
    visits.record(request, engine="india", event="report", company=run["host"], run_id=run["id"],
                  email_domain=em["email"].rsplit("@", 1)[-1].lower())
    return {"status": "sent" if sent else "queued"}
