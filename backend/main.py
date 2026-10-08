"""HTTP API + static web app. Start it with `python run.py`."""
from __future__ import annotations

import secrets

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT, Settings
from .llm import build_llm
from .pipeline import JobManager, run_analysis
from .providers import build_provider
from .storage import Store


class AnalyzeRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=120)
    timezone: str = "UTC"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = Store(settings.db_path)
    jobs = JobManager()
    app = FastAPI(title="Social Climb")

    def require_token(x_app_token: str = Header(default="")) -> None:
        if settings.app_token and not secrets.compare_digest(x_app_token, settings.app_token):
            raise HTTPException(401, "Invalid or missing app token")

    api = Depends(require_token)

    @app.get("/api/config", dependencies=[api])
    def config():
        return {
            "data_provider": settings.data_provider,
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model if settings.llm_provider != "mock" else "mock",
        }

    @app.post("/api/analyze", dependencies=[api])
    def analyze(req: AnalyzeRequest):
        # Build per run so config errors (missing keys) surface as a job error.
        def work(progress):
            return run_analysis(
                req.topic.strip(),
                req.timezone,
                build_provider(settings),
                build_llm(settings),
                store,
                settings.max_hashtags,
                progress,
            )

        return {"job_id": jobs.start(work)}

    @app.get("/api/jobs/{job_id}", dependencies=[api])
    def job(job_id: str):
        found = jobs.get(job_id)
        if not found:
            raise HTTPException(404, "Unknown job")
        return found

    @app.get("/api/reports", dependencies=[api])
    def reports():
        return store.list_reports()

    @app.get("/api/reports/{report_id}", dependencies=[api])
    def report(report_id: str):
        found = store.get_report(report_id)
        if not found:
            raise HTTPException(404, "Unknown report")
        return found

    app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
    return app

