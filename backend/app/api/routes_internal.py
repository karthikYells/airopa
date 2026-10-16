"""Internal surface route (Section 10). This is the only place the GCC Fit
score and third-party names are permitted to appear."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.adapters.llm import LLM
from app.api.abuse import validate
from app.config import get_settings
from app.data.store import save_run
from app.narrative.internal_brief import build_brief
from app.pipeline.orchestrator import run_pipeline

router = APIRouter()


class AssessRequest(BaseModel):
    url: str


# No password on the internal surface, by Airopa's decision (2026-10-17).
# Before hosting, put the internal view behind access control (for example the
# hosting platform's own login) — it exposes GCC Fit, which the public page
# must never show (Section 9.3).
@router.post("/assess")
def assess_company(req: AssessRequest) -> dict:
    settings = get_settings()
    ok, host, reason = validate(req.url)
    if not ok:
        raise HTTPException(status_code=400, detail=f"invalid input: {reason}")

    llm = LLM(settings)
    outcome = run_pipeline(host, settings, llm=llm, surface="internal")
    brief = build_brief(outcome, settings)
    save_run(host, "internal", outcome.terminal_code or "assessed", brief)
    return brief
