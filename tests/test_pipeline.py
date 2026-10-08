from datetime import datetime, timezone

import pytest

from backend.llm import LLMError, MockLLM, parse_json
from backend.pipeline import AnalysisError, run_analysis
from backend.providers.apify import to_post as apify_post
from backend.providers.base import DataProvider, ProviderError
from backend.providers.graph_api import to_post as graph_post
from backend.providers.mock import MockProvider
from backend.storage import Store

NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def test_full_run_with_mocks(tmp_path):
    store = Store(str(tmp_path / "db.sqlite"))
    log = []
    report = run_analysis("Ancient Rome", "Europe/Rome", MockProvider(now=NOW), MockLLM(),
                          store, max_hashtags=5, progress=log.append, now=NOW)
    assert report["plan"]["hashtags"][0] == "ancientrome"
    assert report["stats"]["windows"]["60"]["post_count"] > 100
    assert report["stats"]["timing"] is not None
    assert report["draft"]["caption"]
    assert log[-1] == "Done"
    assert store.list_reports()[0]["topic"] == "Ancient Rome"
    assert store.get_report(report["id"])["topic"] == "Ancient Rome"


def test_history_accumulates_and_dedupes(tmp_path):
    store = Store(str(tmp_path / "db.sqlite"))
    for _ in range(2):
        report = run_analysis("dig", "UTC", MockProvider(now=NOW), MockLLM(), store, 3, now=NOW)
    assert report["stats"]["windows"]["60"]["post_count"] == len(
        store.load_posts(report["plan"]["hashtags"], datetime(2000, 1, 1, tzinfo=timezone.utc), "mock"))


class FailingProvider(DataProvider):
    name = "failing"

    def fetch(self, hashtag, since):
        raise ProviderError(f"blocked #{hashtag}")


def test_all_tags_failing_raises_with_reasons(tmp_path):
    with pytest.raises(AnalysisError, match="blocked"):
        run_analysis("dig", "UTC", FailingProvider(), MockLLM(), Store(str(tmp_path / "d")), 2, now=NOW)


def test_parse_json_tolerates_fences_and_rejects_garbage():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Sure! {"a": 1} hope that helps') == {"a": 1}
    with pytest.raises(LLMError):
        parse_json("no json here")


def test_apify_mapping():
    post = apify_post({
        "id": "1", "shortCode": "abc", "type": "Video", "productType": "clips",
        "caption": "Hi #Dig", "hashtags": ["Dig"], "likesCount": -1, "commentsCount": 4,
        "videoPlayCount": 900, "timestamp": "2026-10-01T10:00:00.000Z", "ownerUsername": "u",
    })
    assert (post.media_type, post.likes, post.views, post.hashtags) == ("reel", 0, 900, ["dig"])
    assert apify_post({"error": "no_items"}) is None


def test_graph_mapping():
    post = graph_post({"id": "9", "media_type": "CAROUSEL_ALBUM", "comments_count": 3,
                       "permalink": "https://instagram.com/p/x", "timestamp": "2026-10-01T10:00:00+0000"})
    assert (post.media_type, post.likes, post.comments) == ("carousel", 0, 3)
