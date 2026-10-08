"""HTTP API + static web app. Start it with `python run.py` (or the packaged SocialClimb.exe)."""
from __future__ import annotations

import io
import secrets
from urllib.parse import quote

import segno
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import WEB_DIR, Settings
from .llm import build_llm
from .network import lan_ip
from .pipeline import JobManager, run_analysis
from .providers import build_provider
from .storage import Store

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


class AnalyzeRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=120)
    timezone: str = "UTC"
    about: str = Field(default="", max_length=2000)


def is_local(request: Request) -> bool:
    return request.client is not None and request.client.host in LOCAL_HOSTS


def create_app(settings: Settings | None = None) -> FastAPI:
    state = {"settings": settings or Settings.from_env()}
    store = Store(state["settings"].db_path)
    jobs = JobManager()
    app = FastAPI(title="Social Climb")

    def require_token(request: Request, x_app_token: str = Header(default="")) -> None:
        """The PC itself is trusted; other devices need the token from the QR code."""
        token = state["settings"].app_token
        if is_local(request) or not token:
            return
        if not secrets.compare_digest(x_app_token, token):
            raise HTTPException(401, "Invalid or missing app token")

    def require_local(request: Request) -> None:
        if not is_local(request):
            raise HTTPException(403, "Settings can only be changed on the computer running Social Climb")

    api = Depends(require_token)

    def phone_url(request: Request) -> str:
        return f"http://{lan_ip()}:{request.url.port or 80}/?token={quote(state['settings'].app_token)}"

    @app.get("/api/config", dependencies=[api])
    def config(request: Request):
        s = state["settings"]
        return {
            "data_provider": s.active_data_provider,
            "llm_provider": s.active_llm_provider,
            "llm_model": s.llm_model if s.active_llm_provider != "mock" else "mock",
            "is_host": is_local(request),
        }

    @app.get("/api/settings", dependencies=[Depends(require_local)])
    def get_settings():
        return state["settings"].public()

    @app.put("/api/settings", dependencies=[Depends(require_local)])
    def put_settings(changes: dict):
        try:
            updated = state["settings"].updated(changes)
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, f"Invalid setting: {exc}") from exc
        updated.save()
        state["settings"] = updated
        return updated.public()

    @app.get("/api/phone", dependencies=[Depends(require_local)])
    def phone(request: Request):
        return {"url": phone_url(request)}

    @app.get("/api/phone/qr.svg", dependencies=[Depends(require_local)])
    def phone_qr(request: Request):
        buf = io.BytesIO()
        segno.make(phone_url(request), error="m").save(buf, kind="svg", scale=6, border=2)
        return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})

    @app.post("/api/analyze", dependencies=[api])
    def analyze(req: AnalyzeRequest):
        settings = state["settings"]

        # Build per run so config errors (missing keys) surface as a job error.
        def work(progress):
            return run_analysis(
                req.topic.strip(),
                req.timezone,
                build_provider(settings),
                build_llm(settings),
                store,
                settings.max_hashtags,
                req.about,
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

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app
