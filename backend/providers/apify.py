"""Apify's managed Instagram hashtag scraper (https://apify.com/apify/instagram-hashtag-scraper).

Apify runs the scraping on its own infrastructure, so your personal Instagram
account is never logged in or put at risk. Billed per result.
"""
from __future__ import annotations

from datetime import datetime

import httpx

from ..models import Post, parse_timestamp
from .base import DataProvider, ProviderError

API = "https://api.apify.com/v2"


def _media_type(item: dict) -> str:
    kind = (item.get("type") or "").lower()
    if item.get("productType") == "clips":
        return "reel"
    if kind == "sidecar":
        return "carousel"
    if kind == "video":
        return "video"
    return "image"


def to_post(item: dict) -> Post | None:
    if not item.get("timestamp") or not (item.get("id") or item.get("shortCode")):
        return None  # error rows / placeholders
    views = item.get("videoPlayCount") or item.get("videoViewCount")
    return Post(
        source="apify",
        id=str(item.get("id") or item.get("shortCode")),
        url=item.get("url") or f"https://www.instagram.com/p/{item.get('shortCode')}/",
        caption=item.get("caption") or "",
        media_type=_media_type(item),
        likes=item.get("likesCount") or 0,
        comments=item.get("commentsCount") or 0,
        views=views,
        posted_at=parse_timestamp(item["timestamp"]),
        owner=item.get("ownerUsername"),
        hashtags=[h.lower() for h in item.get("hashtags") or []],
    )


class ApifyProvider(DataProvider):
    name = "apify"

    def __init__(self, token: str, actor: str, results_per_tag: int, timeout: float = 300):
        if not token:
            raise ProviderError("APIFY_TOKEN is not set")
        self.token = token
        self.actor = actor
        self.results_per_tag = results_per_tag
        self.timeout = timeout

    def fetch(self, hashtag: str, since: datetime) -> list[Post]:
        try:
            resp = httpx.post(
                f"{API}/acts/{self.actor}/run-sync-get-dataset-items",
                params={"token": self.token},
                json={
                    "hashtags": [hashtag],
                    "resultsType": "posts",
                    "resultsLimit": self.results_per_tag,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"Apify returned {exc.response.status_code} for #{hashtag}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Apify request failed for #{hashtag}: {exc}") from exc
        posts = (to_post(item) for item in resp.json())
        return [p for p in posts if p and p.posted_at >= since]
