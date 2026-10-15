"""Airopa GCC Scoring Engine — FastAPI entrypoint.

One engine, two surfaces (Section 9): the public self-serve snapshot and the
internal assessment. CORS is open in dev so the Vite frontend can call it; lock
the allowed origins to the tool's domain in production.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_internal, routes_public
from app.config import get_settings
from app.data.store import init_db

app = FastAPI(
    title="Airopa GCC Scoring Engine",
    version="3.0-build1",
    description="Public snapshot + internal assessment of a company's India GCC opportunity.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict to the tool domain in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_public.router, prefix="/api", tags=["public"])
app.include_router(routes_internal.router, prefix="/api", tags=["internal"])


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "config_version": s.config_version,
        "llm_enabled": s.llm_enabled,
        "use_seed_data": s.use_seed_data,
    }
