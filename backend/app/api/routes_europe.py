"""Europe Market Assessment routes (preview, 19 Oct 2026).

POST /api/europe/score   assess an Indian company's website
POST /api/europe/report  email the PDF; while in preview, only to the
                         addresses in `europe_mail_allow` (others are kept as
                         leads and followed up by hand)
"""
from __future__ import annotations

import json
import logging
import queue
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
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
from app.reports import europe_email
from app.reports.pdf import build_pdf

router = APIRouter()
SURFACE = "europe"
log = logging.getLogger(__name__)


def _public(payload: dict) -> dict:
    """What the page may see: everything except the private block (names)."""
    return {k: v for k, v in payload.items() if k != "_private"}


class ScoreRequest(BaseModel):
    url: str
    # What the company sells, typed by the visitor when we could not read the
    # site or they correct our match. Their own words, checked like a page.
    products: list[str] = Field(default_factory=list, max_length=5)


def _products(req: ScoreRequest) -> list[str]:
    return [p.strip()[:80] for p in req.products if p and p.strip()][:5]


def _rejected(reason: str) -> dict:
    return {"engine": "europe", "mode": "REJECTED", "reason": reason,
            "message": "Enter your company website, for example yourcompany.in."}


def _cached(host: str, request: Request, settings) -> dict | None:
    cached = latest_public_run(host, settings.snapshot_cache_hours, surface=SURFACE)
    if cached is None:
        return None
    visits.record(request, engine="europe", event="check", company=host, run_id=cached["id"],
                  mode=cached["payload"].get("mode"), cached=True)
    public = _public(cached["payload"])
    return {**public, "run_id": cached["id"], "snapshot_token": sign(cached["id"], host, public)}


def _finish(host: str, a, request: Request, corrected: bool) -> dict:
    payload = europe_snapshot.build(a)
    run_id = save_run(host, SURFACE, payload.get("mode"), payload)
    visits.record(request, engine="europe", event="correction" if corrected else "check", company=host,
                  run_id=run_id, mode=payload.get("mode"))
    public = _public(payload)
    return {**public, "run_id": run_id, "snapshot_token": sign(run_id, host, public)}


@router.post("/europe/score")
def europe_score(req: ScoreRequest, request: Request) -> dict:
    settings = get_settings()
    ok, host, reason = validate(req.url)
    if not ok:
        return _rejected(reason)
    products = _products(req)
    if not products and (hit := _cached(host, request, settings)):
        return hit
    limit(request, "europe_score", settings.public_score_limit_per_hour, 3600)
    a = europe_pipeline.run(host, settings, llm=LLM(settings), products=products or None)
    return _finish(host, a, request, bool(products))


@router.post("/europe/score/stream")
def europe_score_stream(req: ScoreRequest, request: Request) -> StreamingResponse:
    """The same check, sent as it happens: one JSON line per finished stage
    ("company", "products"), then "done" with the full page, or "error".
    The open request keeps Cloud Run's CPU on for the whole run, which a
    background job after the response would not have."""
    settings = get_settings()

    def lines(items):
        return StreamingResponse((json.dumps(i, ensure_ascii=False) + "\n" for i in items),
                                 media_type="application/x-ndjson")

    ok, host, reason = validate(req.url)
    if not ok:
        return lines([{"stage": "done", "payload": _rejected(reason)}])
    products = _products(req)
    if not products and (hit := _cached(host, request, settings)):
        return lines([{"stage": "done", "payload": hit}])
    limit(request, "europe_score", settings.public_score_limit_per_hour, 3600)

    q: queue.Queue = queue.Queue()

    def work() -> None:
        try:
            a = europe_pipeline.run(host, settings, llm=LLM(settings), products=products or None,
                                    on_stage=lambda st, a: q.put(europe_snapshot.preview(st, a)))
            q.put({"stage": "done", "payload": _finish(host, a, request, bool(products))})
        except Exception:
            log.exception("europe stream failed for %s", host)
            q.put({"stage": "error", "message": "Something went wrong while checking. Please try again."})
        finally:
            q.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while True:
            try:
                item = q.get(timeout=15)
            except queue.Empty:
                yield "\n"                       # keeps proxies from closing a quiet connection
                continue
            if item is None:
                return
            yield json.dumps(item, ensure_ascii=False) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
    # "*" sends to every work address (public launch); personal addresses are
    # always followed up by a person first, as on the India engine.
    if em["personal"]:
        sent, detail = False, "personal email: manual follow-up"
    elif "*" in allowed or domain in allowed:
        link = f"{settings.europe_site_url}?company={run['host']}"
        subject, text, html = europe_email.build_email(payload, req.name, link)
        sent, detail = mailer.send(settings, em["email"], subject, text, html, pdf,
                                   f"Europe-Market-Assessment-{run['host']}.pdf",
                                   bcc=settings.mail_notify or None)
    else:
        sent, detail = False, "preview: not on the send list, follow up by hand"
    save_lead(engine="europe", run_id=run["id"], host=run["host"], name=req.name, email=em["email"],
              email_type="personal" if em["personal"] else "work", company=req.company,
              role=req.role or None, call_partner="yes" if req.call_partner else "no",
              status="sent" if sent else "queued", detail=detail)
    visits.record(request, engine="europe", event="report", company=run["host"], run_id=run["id"],
                  email_domain=domain)
    return {"status": "sent" if sent else "queued"}
