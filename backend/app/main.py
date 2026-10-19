"""Airopa GCC Scoring Engine — FastAPI entrypoint.

One engine, two surfaces (Section 9): the public self-serve snapshot and the
internal assessment. CORS is open in dev so the Vite frontend can call it; lock
the allowed origins to the tool's domain in production.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_europe, routes_internal, routes_public, routes_tasks
from app.config import get_settings
from app.data.store import init_db

app = FastAPI(
    title="Airopa GCC Scoring Engine",
    version="3.0-build1",
    description="Public snapshot + internal assessment of a company's India GCC opportunity.",
)

# In production CORS_ORIGINS=https://accessindia.nl so only the site's page can
# call the engine from a browser; "*" is for local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)

app.include_router(routes_public.router, prefix="/api", tags=["public"])
app.include_router(routes_internal.router, prefix="/api", tags=["internal"])
app.include_router(routes_tasks.router, prefix="/api", tags=["tasks"])
app.include_router(routes_europe.router, prefix="/api", tags=["europe"])

# Europe Market Assessment preview page, served by the engine itself until the
# accessindia.nl page goes live (built from frontend/ with VITE_ENGINE=europe).
_PREVIEW = Path(__file__).resolve().parent / "static" / "europe-preview"
if _PREVIEW.exists():
    app.mount("/preview/europe", StaticFiles(directory=_PREVIEW, html=True), name="europe-preview")


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
