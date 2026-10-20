"""Europe Market Assessment routes (preview, 19 Oct 2026).

POST /api/europe/score   assess an Indian company's website
POST /api/europe/report  email the PDF; while in preview, only to the
                         addresses in `europe_mail_allow` (others are kept as
                         leads and followed up by hand)
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.adapters import mailer
from app.adapters.llm import LLM
from app.api.abuse import validate
from app.api.email_check import check_email
from app.api.ratelimit import limit
from app.api import visits
from app.api.signing import sign, verify
from app.config import get_settings
from app.data.store import get_run, latest_public_run, save_lead, save_run
from app.narrative import europe_snapshot
from app.pipeline import europe as europe_pipeline
from app.reports.pdf import build_pdf

router = APIRouter()
SURFACE = "europe"


class ScoreRequest(BaseModel):
    url: str


@router.post("/europe/score")
def europe_score(req: ScoreRequest, request: Request) -> dict:
    settings = get_settings()
    ok, host, reason = validate(req.url)
    if not ok:
        return {"engine": "europe", "mode": "REJECTED", "reason": reason,
                "message": "Enter your company website, for example yourcompany.in."}
    cached = latest_public_run(host, settings.snapshot_cache_hours, surface=SURFACE)
    if cached is not None:
        visits.record(request, engine="europe", event="check", company=host, run_id=cached["id"],
                      mode=cached["payload"].get("mode"), cached=True)
        return {**cached["payload"], "run_id": cached["id"],
                "snapshot_token": sign(cached["id"], host, cached["payload"])}
    limit(request, "europe_score", settings.public_score_limit_per_hour, 3600)
    a = europe_pipeline.run(host, settings, llm=LLM(settings))
    payload = europe_snapshot.build(a)
    run_id = save_run(host, SURFACE, payload.get("mode"), payload)
    visits.record(request, engine="europe", event="check", company=host, run_id=run_id, mode=payload.get("mode"))
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
    bot_field: str = ""


@router.post("/europe/report")
def europe_report(req: ReportRequest, request: Request) -> dict:
    settings = get_settings()
    if req.bot_field:
        return {"status": "sent"}
    limit(request, "europe_report", settings.report_limit_per_hour, 3600)
    em = check_email(req.email)
    if not em["ok"]:
        raise HTTPException(status_code=422, detail="invalid_email")
    if em["personal"] and not req.allow_personal:
        raise HTTPException(status_code=422, detail="personal_email")
    run = get_run(req.run_id)
    if run is None or run["surface"] != SURFACE:
        signed = verify(req.snapshot_token) if req.snapshot_token else None
        if signed is None or signed.get("id") != req.run_id:
            raise HTTPException(status_code=404, detail="snapshot_not_found")
        run = {"id": signed["id"], "host": signed["host"], "payload": signed["payload"]}
    payload = run["payload"]
    pdf = build_pdf(payload, recipient_name=req.name)
    Path("data/reports").mkdir(parents=True, exist_ok=True)
    (Path("data/reports") / f"{run['id']}.pdf").write_bytes(pdf)

    domain = em["email"].rsplit("@", 1)[-1].lower()
    allowed = [d.strip().lower() for d in settings.europe_mail_allow.split(",") if d.strip()]
    sent, detail = False, "preview: not on the send list, follow up by hand"
    if domain in allowed:
        subject = f"Your Europe Market Assessment: {payload.get('company', {}).get('name') or run['host']}"
        text = (f"Dear {req.name},\n\nAttached is the Europe Market Assessment for "
                f"{payload.get('company', {}).get('name') or run['host']}.\n\nAccess India Netherlands, "
                "with founding partner Airopa Global")
        html = "<p>" + text.replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"
        sent, detail = mailer.send(settings, em["email"], subject, text, html, pdf,
                                   f"Europe-Market-Assessment-{run['host']}.pdf",
                                   bcc=settings.mail_notify or None)
    save_lead(run_id=run["id"], host=run["host"], name=req.name, email=em["email"],
              email_type="personal" if em["personal"] else "work", company=req.company,
              role=req.role or None, call_partner="yes" if req.call_partner else "no",
              status="sent" if sent else "queued", detail=detail)
    visits.record(request, engine="europe", event="report", company=run["host"], run_id=run["id"],
                  email_domain=domain)
    return {"status": "sent" if sent else "queued"}
