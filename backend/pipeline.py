"""Orchestrates one analysis run and tracks background jobs."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

from . import agents
from .analysis import WINDOWS, analyze
from .llm import LLM
from .providers import DataProvider, ProviderError
from .storage import Store


class AnalysisError(RuntimeError):
    pass


def run_analysis(
    topic: str,
    tz_name: str,
    provider: DataProvider,
    llm: LLM,
    store: Store,
    max_hashtags: int,
    progress: Callable[[str], None] = lambda _msg: None,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=max(WINDOWS))

    progress(f"Planning searches for '{topic}'")
    plan = agents.plan_search(llm, topic, max_hashtags)
    progress("Hashtags: " + ", ".join(f"#{t}" for t in plan["hashtags"]))

    warnings = []
    for tag in plan["hashtags"]:
        progress(f"Collecting posts for #{tag}")
        try:
            posts = provider.fetch(tag, since)
        except ProviderError as exc:
            warnings.append(str(exc))
            progress(f"Skipped #{tag}: {exc}")
            continue
        store.save_posts(tag, posts)
        progress(f"#{tag}: {len(posts)} posts")

    posts = store.load_posts(plan["hashtags"], since, provider.name)
    if not posts:
        raise AnalysisError("No posts found for any hashtag. " + " ".join(warnings))

    progress(f"Analyzing {len(posts)} posts")
    stats = analyze(posts, now, tz_name)

    progress("Drafting your post")
    draft = agents.draft_post(llm, topic, stats)

    report = {
        "topic": topic,
        "generated_at": now.isoformat(),
        "data_source": provider.name,
        "plan": plan,
        "stats": stats,
        "draft": draft,
        "warnings": warnings,
    }
    store.save_report(report)
    progress("Done")
    return report


class JobManager:
    """Runs analyses on background threads; state lives in memory."""

    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, work: Callable[[Callable[[str], None]], dict]) -> str:
        job_id = uuid.uuid4().hex
        job = {"id": job_id, "status": "running", "log": [], "report": None, "error": None}
        with self._lock:
            self._jobs[job_id] = job

        def target():
            try:
                job["report"] = work(job["log"].append)
                job["status"] = "done"
            except Exception as exc:  # surfaced to the UI
                job["error"] = str(exc)
                job["status"] = "error"

        threading.Thread(target=target, daemon=True).start()
        return job_id

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return {**job, "log": list(job["log"])} if job else None
