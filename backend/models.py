"""Normalized post record shared by every data provider."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)

# Comments are rarer and a stronger signal than likes, so they count double.
COMMENT_WEIGHT = 2


def extract_hashtags(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for tag in HASHTAG_RE.findall(text or ""):
        seen.setdefault(tag.lower(), None)
    return list(seen)


def parse_timestamp(value: str | int | float) -> datetime:
    """Parse ISO-8601 (incl. '+0000' and 'Z' suffixes) or unix seconds to aware UTC."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    text = value.strip().replace("Z", "+00:00")
    if re.search(r"[+-]\d{4}$", text):
        text = f"{text[:-2]}:{text[-2:]}"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass
class Post:
    source: str
    id: str
    url: str
    caption: str
    media_type: str  # image | carousel | video | reel
    likes: int
    comments: int
    posted_at: datetime  # aware, UTC
    views: int | None = None
    owner: str | None = None
    hashtags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.hashtags:
            self.hashtags = extract_hashtags(self.caption)
        # Some sources report hidden like counts as -1.
        self.likes = max(int(self.likes or 0), 0)
        self.comments = max(int(self.comments or 0), 0)
        if self.views is not None and self.views < 0:
            self.views = None

    @property
    def score(self) -> int:
        return self.likes + COMMENT_WEIGHT * self.comments

    def to_dict(self) -> dict:
        data = asdict(self)
        data["posted_at"] = self.posted_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Post":
        return cls(**{**data, "posted_at": parse_timestamp(data["posted_at"])})
