"""SQLite cache of scraped posts and generated reports.

Posts are kept between runs so history accumulates, which matters for sources
(like the Graph API) that only expose a short slice of recent data.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .models import Post

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    source TEXT NOT NULL,
    id TEXT NOT NULL,
    posted_at TEXT NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (source, id)
);
CREATE TABLE IF NOT EXISTS post_tags (
    source TEXT NOT NULL,
    id TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (source, id, tag)
);
CREATE INDEX IF NOT EXISTS post_tags_tag ON post_tags (tag);
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save_posts(self, tag: str, posts: list[Post]) -> None:
        with self._conn() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO posts VALUES (?, ?, ?, ?)",
                [(p.source, p.id, p.posted_at.isoformat(), json.dumps(p.to_dict())) for p in posts],
            )
            conn.executemany(
                "INSERT OR IGNORE INTO post_tags VALUES (?, ?, ?)",
                [(p.source, p.id, tag) for p in posts],
            )

    def load_posts(self, tags: list[str], since: datetime, source: str) -> list[Post]:
        if not tags:
            return []
        marks = ",".join("?" * len(tags))
        with self._conn() as conn:
            rows = conn.execute(
                f"""SELECT DISTINCT p.data FROM posts p
                    JOIN post_tags t ON t.source = p.source AND t.id = p.id
                    WHERE t.tag IN ({marks}) AND p.source = ? AND p.posted_at >= ?""",
                [*tags, source, since.astimezone(timezone.utc).isoformat()],
            ).fetchall()
        return [Post.from_dict(json.loads(row[0])) for row in rows]

    def save_report(self, report: dict) -> str:
        report_id = report.setdefault("id", uuid.uuid4().hex)
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO reports VALUES (?, ?, ?, ?)",
                (report_id, report["topic"], report["generated_at"], json.dumps(report)),
            )
        return report_id

    def list_reports(self, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, topic, created_at FROM reports ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [{"id": r[0], "topic": r[1], "generated_at": r[2]} for r in rows]

    def get_report(self, report_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT data FROM reports WHERE id = ?", (report_id,)).fetchone()
        return json.loads(row[0]) if row else None
