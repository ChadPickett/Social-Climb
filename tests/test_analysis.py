from datetime import datetime, timedelta, timezone

from backend.analysis import analyze, percentile
from backend.models import Post, parse_timestamp

NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def make(i, days_ago, likes, fmt="image", hour=12, comments=0, caption="#dig"):
    posted = (NOW - timedelta(days=days_ago)).replace(hour=hour)
    return Post("t", str(i), f"https://x/{i}", caption, fmt, likes, comments, posted)


def test_parse_timestamp_variants():
    expected = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert parse_timestamp("2026-01-02T03:04:05+0000") == expected
    assert parse_timestamp("2026-01-02T03:04:05.000Z") == expected
    assert parse_timestamp("2026-01-02T05:04:05+02:00") == expected


def test_percentile_interpolates():
    assert percentile([1, 2, 3, 4], 0.5) == 2.5
    assert percentile([], 0.5) is None


def test_windows_include_only_recent_posts():
    posts = [make(1, 3, 10), make(2, 10, 10), make(3, 20, 10), make(4, 45, 10), make(5, 90, 10)]
    stats = analyze(posts, NOW)
    counts = {d: w["post_count"] for d, w in stats["windows"].items()}
    assert counts == {"7": 1, "15": 2, "30": 3, "60": 4}


def test_finds_best_hour_format_and_goals():
    posts = []
    for i in range(40):
        evening = i % 2 == 0
        posts.append(make(i, 1 + i % 25, 1000 if evening else 100,
                          fmt="reel" if evening else "image", hour=19 if evening else 8))
    stats = analyze(posts, NOW, "UTC")
    assert stats["primary_window_days"] == 30
    assert stats["timing"]["best_hour"] == 19
    assert stats["best_format"] == "reel"
    assert stats["goals"]["likes"]["target"] == 1000
    assert datetime.fromisoformat(stats["timing"]["next_slot"]) > NOW


def test_timezone_shifts_hours_and_bad_timezone_falls_back():
    posts = [make(i, 1 + i % 20, 500, hour=19) for i in range(30)]
    assert analyze(posts, NOW, "America/New_York")["timing"]["best_hour"] in (14, 15)
    assert analyze(posts, NOW, "Not/AZone")["timezone"] == "UTC"


def test_hidden_like_counts_are_clamped():
    assert make(1, 1, -1).likes == 0
