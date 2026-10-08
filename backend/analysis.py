"""Deterministic performance statistics.

All numbers in a report (timing, goals, benchmarks) come from here, not from
the LLM, so they are reproducible and can't be hallucinated.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import median
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import Post

WINDOWS = (7, 15, 30, 60)
# Window used for timing + goals: the first with enough posts, in this order.
PRIMARY_PREFERENCE = (30, 60, 15, 7)
MIN_PRIMARY_POSTS = 20
# A day/hour/format needs this many posts before it can be called "best".
MIN_BUCKET_POSTS = 5
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _dist(values: list[float]) -> dict | None:
    if not values:
        return None
    return {
        "median": round(percentile(values, 0.5)),
        "p75": round(percentile(values, 0.75)),
        "p90": round(percentile(values, 0.9)),
    }


def _ranked_buckets(posts: list[Post], key, label) -> list[dict]:
    """Median score per bucket, ignoring buckets too small to trust."""
    groups: dict = defaultdict(list)
    for p in posts:
        groups[key(p)].append(p.score)
    min_count = max(MIN_BUCKET_POSTS, math.ceil(len(posts) * 0.04))
    rows = [
        {**label(k), "count": len(v), "median_score": round(median(v))}
        for k, v in groups.items() if len(v) >= min_count
    ]
    return sorted(rows, key=lambda r: r["median_score"], reverse=True)


def account(p: Post) -> str:
    """Who made the post; posts with unknown owners count as separate accounts."""
    return p.owner or f"post:{p.id}"


def diverse_top(posts: list[Post], limit: int, per_account: int = 1) -> list[Post]:
    """Best posts by score, capped per account so one viral creator can't dominate."""
    seen: Counter = Counter()
    picked = []
    for p in sorted(posts, key=lambda p: p.score, reverse=True):
        if seen[account(p)] < per_account:
            seen[account(p)] += 1
            picked.append(p)
            if len(picked) == limit:
                break
    return picked


def _caption_bucket(p: Post) -> str:
    n = len(p.caption)
    return "short (<100 chars)" if n < 100 else "medium (100-500)" if n <= 500 else "long (>500)"


def summarize(posts: list[Post], tz: ZoneInfo) -> dict:
    if not posts:
        return {"post_count": 0}
    local = lambda p: p.posted_at.astimezone(tz)  # noqa: E731
    top_quartile = diverse_top(posts, max(1, len(posts) // 4), per_account=2)
    # Count accounts, not posts, so one account repeating its own tags doesn't rank them.
    tag_counts = Counter(t for _acct, t in {(account(p), t) for p in top_quartile for t in p.hashtags})
    by_format = _ranked_buckets(posts, lambda p: p.media_type, lambda k: {"format": k})
    for row in by_format:
        row["share"] = round(row["count"] / len(posts), 2)
    return {
        "post_count": len(posts),
        "likes": _dist([p.likes for p in posts]),
        "comments": _dist([p.comments for p in posts]),
        "views": _dist([p.views for p in posts if p.views]),
        "score": _dist([p.score for p in posts]),
        "by_format": by_format,
        "by_hour": _ranked_buckets(posts, lambda p: local(p).hour, lambda k: {"hour": k}),
        "by_weekday": _ranked_buckets(
            posts, lambda p: local(p).weekday(), lambda k: {"weekday": WEEKDAYS[k]}
        ),
        "by_caption_length": _ranked_buckets(posts, _caption_bucket, lambda k: {"length": k}),
        "top_hashtags": [{"tag": t, "accounts": c} for t, c in tag_counts.most_common(15)],
        "top_posts": [
            {
                "url": p.url,
                "owner": p.owner,
                "format": p.media_type,
                "likes": p.likes,
                "comments": p.comments,
                "views": p.views,
                "posted_at": local(p).isoformat(),
                "caption": p.caption[:280],
            }
            for p in diverse_top(posts, 5)
        ],
    }


def _next_slot(now: datetime, tz: ZoneInfo, weekday: int | None, hour: int) -> datetime:
    local_now = now.astimezone(tz)
    candidate = local_now.replace(hour=hour, minute=0, second=0, microsecond=0)
    for _ in range(8):
        if candidate > local_now and (weekday is None or candidate.weekday() == weekday):
            return candidate
        candidate += timedelta(days=1)
    return candidate


def _goal(dist: dict | None) -> dict | None:
    if not dist:
        return None
    return {"baseline": dist["median"], "target": dist["p75"], "stretch": dist["p90"]}


def analyze(posts: list[Post], now: datetime, tz_name: str = "UTC") -> dict:
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        tz, tz_name = ZoneInfo("UTC"), "UTC"

    windows = {
        str(days): summarize([p for p in posts if p.posted_at >= now - timedelta(days=days)], tz)
        for days in WINDOWS
    }
    primary_days = next(
        (d for d in PRIMARY_PREFERENCE if windows[str(d)]["post_count"] >= MIN_PRIMARY_POSTS),
        max(WINDOWS, key=lambda d: windows[str(d)]["post_count"]),
    )
    primary = windows[str(primary_days)]

    timing = None
    if primary.get("by_hour"):
        hour = primary["by_hour"][0]["hour"]
        day_name = primary["by_weekday"][0]["weekday"] if primary["by_weekday"] else None
        day = WEEKDAYS.index(day_name) if day_name else None
        timing = {
            "best_weekday": day_name,
            "best_hour": hour,
            "top_hours": [r["hour"] for r in primary["by_hour"][:3]],
            "top_weekdays": [r["weekday"] for r in primary["by_weekday"][:3]],
            "next_slot": _next_slot(now, tz, day, hour).isoformat(),
        }

    short, long_ = windows["7"].get("score"), windows["60"].get("score")
    momentum = round(short["median"] / long_["median"], 2) if short and long_ and long_["median"] else None

    return {
        "timezone": tz_name,
        "primary_window_days": primary_days,
        "windows": windows,
        "timing": timing,
        "goals": {
            "likes": _goal(primary.get("likes")),
            "comments": _goal(primary.get("comments")),
            "views": _goal(primary.get("views")),
        },
        "best_format": primary["by_format"][0]["format"] if primary.get("by_format") else None,
        "momentum_7d_vs_60d": momentum,
    }
