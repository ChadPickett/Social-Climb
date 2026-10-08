import json
from datetime import datetime, timedelta, timezone

from backend import agents
from backend.analysis import analyze, diverse_top
from backend.llm import LLM
from backend.models import Post

NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def post(i, owner, likes, caption="#dig"):
    return Post("t", str(i), f"https://x/{i}", caption, "carousel", likes, 0, NOW - timedelta(days=1 + i % 20), owner=owner)


class ScriptedLLM(LLM):
    """Returns queued responses per task and records what it was sent."""

    def __init__(self, **responses):
        self.responses = {k: list(v) for k, v in responses.items()}
        self.calls = []

    def complete_json(self, task, system, user):
        self.calls.append((task, json.loads(user)))
        return self.responses[task].pop(0)


def idea(title, caption="A standalone caption #dig #history"):
    return {"title": title, "hook": title, "caption": caption, "hashtags": ["#Dig", "dig", "history!"]}


def test_diverse_top_caps_each_account():
    posts = [post(i, "viral", 1000 - i) for i in range(5)] + [post(10 + i, f"a{i}", 10) for i in range(3)]
    picked = diverse_top(posts, limit=10, per_account=2)
    assert [p.owner for p in picked] == ["viral", "viral", "a0", "a1", "a2"]


def test_top_hashtags_count_accounts_not_posts():
    posts = [post(i, "spammer", 1000, "#onlyme #dig") for i in range(10)]
    posts += [post(20 + i, f"a{i}", 900, "#dig") for i in range(3)]
    tags = {t["tag"]: t["accounts"] for t in analyze(posts, NOW)["windows"]["30"]["top_hashtags"]}
    assert tags["onlyme"] == 1 and tags["dig"] >= 2


def test_themes_backed_by_one_account_are_dropped():
    sample = [post(1, "viral", 1000), post(2, "viral", 900), post(3, "other", 800)]
    llm = ScriptedLLM(themes=[{"themes": [
        {"name": "Viral series", "description": "x", "post_numbers": [1, 2]},
        {"name": "Shared", "description": "y", "post_numbers": [1, 3, 99, "2"]},
    ]}])
    result = agents.find_themes(llm, "dig", sample)
    assert [(t["name"], t["accounts"]) for t in result["themes"]] == [("Shared", 2)]


def test_sequel_ideas_trigger_retry_and_are_never_returned():
    stats = analyze([post(i, f"a{i}", 100) for i in range(30)], NOW)
    llm = ScriptedLLM(ideas=[
        {"ideas": [idea("Unwritten rules: Part 2"), idea("Fresh idea")]},
        {"ideas": [idea("Rules pt. 3"), idea("Another fresh idea"), idea("Third idea")], "posting_notes": "n"},
    ])
    result = agents.write_ideas(llm, "dig", stats, {"themes": []}, about="I have 6 dig photos")
    assert [i["title"] for i in result["ideas"]] == ["Another fresh idea", "Third idea"]
    assert "correction" in llm.calls[1][1]
    assert llm.calls[0][1]["creator_and_material"] == "I have 6 dig photos"
    # The writer never receives raw captions of other people's posts.
    assert "example_top_captions" not in json.dumps(llm.calls[0][1])


def test_ideas_have_hashtags_only_in_the_list():
    stats = analyze([post(i, f"a{i}", 100) for i in range(30)], NOW)
    llm = ScriptedLLM(ideas=[{"ideas": [idea("Fresh", "Line one #dig\n\n#history #artifact")]}])
    only = agents.write_ideas(llm, "dig", stats, {"themes": []})["ideas"][0]
    assert only["caption"] == "Line one"
    assert only["hashtags"] == ["dig", "history"]


def test_sequel_detection():
    for text in ["Part 2", "part two", "Pt. 3", "the sequel", "Round 2", "continued from"]:
        assert agents._is_sequel({"title": text}), text
    for text in ["Part of the team", "2 things to know", "Top 10 finds"]:
        assert not agents._is_sequel({"title": text}), text
