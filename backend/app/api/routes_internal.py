"""Internal surface route (Section 10). Token-gated. This is the only place the
GCC Fit score and third-party names are permitted to appear."""
from __future__ import annotations

import hmac
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
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


def _check_auth(token: Optional[str]) -> None:
    """Fails closed: with no INTERNAL_API_TOKEN configured the internal surface
    is refused, so a deployment that forgets the setting cannot leak GCC Fit."""
    settings = get_settings()
    if not settings.internal_api_token:
        raise HTTPException(status_code=503,
                            detail="internal view disabled: set INTERNAL_API_TOKEN in backend/.env")
    if not token or not hmac.compare_digest(token.encode(), settings.internal_api_token.encode()):
        raise HTTPException(status_code=401, detail="invalid internal password")


@router.post("/assess")
def assess_company(req: AssessRequest,
                   x_internal_token: Optional[str] = Header(default=None)) -> dict:
    _check_auth(x_internal_token)
    settings = get_settings()
    ok, host, reason = validate(req.url)
    if not ok:
        raise HTTPException(status_code=400, detail=f"invalid input: {reason}")

    llm = LLM(settings)
    outcome = run_pipeline(host, settings, llm=llm, surface="internal")
    brief = build_brief(outcome, settings)
    save_run(host, "internal", outcome.terminal_code or "assessed", brief)
    return brief
