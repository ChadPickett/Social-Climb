"""Synthetic data so the whole app can be exercised without accounts or keys.

The generator bakes in patterns (reels and carousels outperform, evenings and
Tue/Thu do well) so the analysis has something real to find.
"""
from __future__ import annotations

import math
import random
import zlib
from datetime import datetime, timedelta, timezone

from ..models import Post
from .base import DataProvider

FORMAT_BOOST = {"reel": 2.2, "carousel": 1.5, "image": 1.0, "video": 1.2}
WEEKDAY_BOOST = {1: 1.25, 3: 1.2}  # Tue, Thu


class MockProvider(DataProvider):
    name = "mock"

    def __init__(self, posts_per_tag: int = 160, now: datetime | None = None):
        self.posts_per_tag = posts_per_tag
        self.now = now

    def fetch(self, hashtag: str, since: datetime) -> list[Post]:
        rng = random.Random(zlib.crc32(hashtag.encode()))
        now = self.now or datetime.now(timezone.utc)
        posts = []
        for i in range(self.posts_per_tag):
            posted = now - timedelta(minutes=rng.randint(0, 60 * 24 * 60))
            if posted < since:
                continue
            fmt = rng.choices(list(FORMAT_BOOST), weights=[4, 3, 3, 1])[0]
            hour = posted.hour
            evening = 1.6 if 17 <= hour <= 21 else (0.7 if 1 <= hour <= 6 else 1.0)
            boost = FORMAT_BOOST[fmt] * evening * WEEKDAY_BOOST.get(posted.weekday(), 1.0)
            likes = int(math.exp(rng.gauss(6.0, 0.9)) * boost)
            extra = rng.sample(["history", "explore", "learn", "travel", "science", "didyouknow"], 2)
            caption = (
                f"Post {i} about {hashtag}. " + "Long story. " * rng.randint(0, 60)
                + " ".join(f"#{t}" for t in [hashtag, *extra])
            )
            posts.append(Post(
                source=self.name,
                id=f"{hashtag}-{i}",
                url=f"https://www.instagram.com/p/mock{hashtag}{i}/",
                caption=caption,
                media_type=fmt,
                likes=likes,
                comments=int(likes * rng.uniform(0.01, 0.06)),
                views=int(likes * rng.uniform(15, 40)) if fmt in ("reel", "video") else None,
                posted_at=posted,
                owner=f"creator_{rng.randint(1, 40)}",
            ))
        return posts
