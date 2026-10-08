"""Settings loaded from environment variables (and an optional .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader: KEY=VALUE lines; real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    data_provider: str = "mock"
    apify_token: str = ""
    apify_actor: str = "apify~instagram-hashtag-scraper"
    apify_results_per_tag: int = 150
    ig_graph_token: str = ""
    ig_user_id: str = ""
    ig_graph_version: str = "v21.0"
    llm_provider: str = "mock"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    app_token: str = ""
    db_path: str = str(ROOT / "data" / "social_climb.db")
    max_hashtags: int = 8

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv(ROOT / ".env")
        env = os.environ.get
        return cls(
            data_provider=env("DATA_PROVIDER", "mock").lower(),
            apify_token=env("APIFY_TOKEN", ""),
            apify_actor=env("APIFY_ACTOR", cls.apify_actor),
            apify_results_per_tag=int(env("APIFY_RESULTS_PER_TAG", "150")),
            ig_graph_token=env("IG_GRAPH_TOKEN", ""),
            ig_user_id=env("IG_USER_ID", ""),
            ig_graph_version=env("IG_GRAPH_VERSION", cls.ig_graph_version),
            llm_provider=env("LLM_PROVIDER", "mock").lower(),
            llm_base_url=env("LLM_BASE_URL", cls.llm_base_url),
            llm_api_key=env("LLM_API_KEY", ""),
            llm_model=env("LLM_MODEL", cls.llm_model),
            app_token=env("APP_TOKEN", ""),
            db_path=env("DB_PATH", "") or cls.db_path,
            max_hashtags=int(env("MAX_HASHTAGS", "8")),
        )
