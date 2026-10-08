"""Official Instagram Graph API hashtag search.

Free and within Instagram's terms, but limited: needs a Business/Creator
account, allows 30 unique hashtags per rolling 7 days, and only exposes each
hashtag's current top posts plus the last 24h of recent posts. Posts are stored
locally on every run, so the 15/30/60-day history builds up over time.
"""
from __future__ import annotations

from datetime import datetime

import httpx

from ..models import Post, parse_timestamp
from .base import DataProvider, ProviderError

FIELDS = "id,caption,comments_count,like_count,media_type,permalink,timestamp"
MEDIA_TYPES = {"CAROUSEL_ALBUM": "carousel", "VIDEO": "video", "IMAGE": "image"}


def to_post(item: dict) -> Post:
    return Post(
        source="graph",
        id=item["id"],
        url=item.get("permalink", ""),
        caption=item.get("caption") or "",
        media_type=MEDIA_TYPES.get(item.get("media_type", ""), "image"),
        likes=item.get("like_count") or 0,
        comments=item.get("comments_count") or 0,
        posted_at=parse_timestamp(item["timestamp"]),
    )


class GraphApiProvider(DataProvider):
    name = "graph"

    def __init__(self, token: str, user_id: str, version: str, max_pages: int = 4):
        if not token or not user_id:
            raise ProviderError("IG_GRAPH_TOKEN and IG_USER_ID must both be set")
        self.base = f"https://graph.facebook.com/{version}"
        self.params = {"access_token": token, "user_id": user_id}
        self.max_pages = max_pages

    def _get(self, url: str, params: dict | None = None) -> dict:
        try:
            resp = httpx.get(url, params=params, timeout=30)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Graph API request failed: {exc}") from exc
        data = resp.json()
        if resp.status_code >= 400 or "error" in data:
            message = data.get("error", {}).get("message", resp.text[:200])
            raise ProviderError(f"Graph API error: {message}")
        return data

    def fetch(self, hashtag: str, since: datetime) -> list[Post]:
        found = self._get(f"{self.base}/ig_hashtag_search", {**self.params, "q": hashtag})
        if not found.get("data"):
            return []
        tag_id = found["data"][0]["id"]
        posts: dict[str, Post] = {}
        for edge in ("top_media", "recent_media"):
            url, params = f"{self.base}/{tag_id}/{edge}", {**self.params, "fields": FIELDS, "limit": 50}
            for _ in range(self.max_pages):
                page = self._get(url, params)
                for item in page.get("data", []):
                    if "timestamp" in item:
                        post = to_post(item)
                        if post.posted_at >= since:
                            posts[post.id] = post
                url, params = page.get("paging", {}).get("next"), None
                if not url:
                    break
        return list(posts.values())
