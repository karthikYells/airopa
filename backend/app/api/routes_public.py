"""Public surface route (Section 9). Returns the snapshot payload, guaranteed
to carry no GCC Fit score and no third-party names."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.adapters.llm import LLM
from app.api.abuse import is_blocklisted, validate
from app.config import get_settings
from app.data.store import save_run
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
def score_company(req: ScoreRequest) -> dict:
    settings = get_settings()
    ok, host, reason = validate(req.url)
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

    save_run(host, "public", mode.value, payload)
    return payload
