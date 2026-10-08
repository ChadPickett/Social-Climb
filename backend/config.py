"""Settings: defaults < environment / .env < settings saved from the app's Settings screen."""
from __future__ import annotations

import json
import os
import secrets
import sys
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)  # running as the packaged .exe
# Where bundled files (web/) live: the PyInstaller unpack dir, or the repo root.
BUNDLE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
WEB_DIR = BUNDLE / "web"

# Fields the Settings screen may change. Secrets are never sent back to the browser.
EDITABLE = {
    "data_provider", "apify_token", "apify_results_per_tag",
    "llm_provider", "llm_base_url", "llm_api_key", "llm_model", "max_hashtags",
}
SECRETS = {"apify_token", "llm_api_key"}


def data_dir() -> Path:
    if os.environ.get("DATA_DIR"):
        return Path(os.environ["DATA_DIR"])
    if FROZEN:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or Path.home()
        return Path(base) / "SocialClimb"
    return BUNDLE / "data"


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
    data_provider: str = "auto"  # auto | mock | apify | graph
    apify_token: str = ""
    apify_actor: str = "apify~instagram-hashtag-scraper"
    apify_results_per_tag: int = 50
    ig_graph_token: str = ""
    ig_user_id: str = ""
    ig_graph_version: str = "v21.0"
    llm_provider: str = "auto"  # auto | mock | openai (any OpenAI-compatible API)
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    # Required from other devices (the phone gets it via the QR code). Requests
    # from this computer itself never need it.
    app_token: str = ""
    db_path: str = ""
    max_hashtags: int = 8

    @property
    def active_data_provider(self) -> str:
        if self.data_provider == "auto":
            return "apify" if self.apify_token else "mock"
        return self.data_provider

    @property
    def active_llm_provider(self) -> str:
        if self.llm_provider == "auto":
            return "openai" if self.llm_api_key else "mock"
        return self.llm_provider

    @property
    def settings_path(self) -> Path:
        return Path(self.db_path).parent / "settings.json"

    def updated(self, changes: dict) -> "Settings":
        """Apply edits from the Settings screen. Blank values mean 'keep current'."""
        types = {f.name: f.type for f in fields(self)}
        clean = {}
        for key, value in changes.items():
            if key not in EDITABLE or value is None or value == "":
                continue
            clean[key] = int(value) if types[key] == "int" else str(value).strip()
        return replace(self, **clean)

    def save(self) -> None:
        path = self.settings_path
        path.parent.mkdir(parents=True, exist_ok=True)
        saved = {k: v for k, v in asdict(self).items() if k in EDITABLE | {"app_token"}}
        path.write_text(json.dumps(saved, indent=2), encoding="utf-8")

    def public(self) -> dict:
        """Editable values safe to show in the browser (secrets reduced to set/unset)."""
        data = {k: getattr(self, k) for k in EDITABLE - SECRETS}
        data.update({f"{k}_set": bool(getattr(self, k)) for k in SECRETS})
        return data

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv(BUNDLE / ".env")
        env = os.environ.get
        base = cls(
            data_provider=env("DATA_PROVIDER", "auto").lower(),
            apify_token=env("APIFY_TOKEN", ""),
            apify_actor=env("APIFY_ACTOR", cls.apify_actor),
            apify_results_per_tag=int(env("APIFY_RESULTS_PER_TAG", str(cls.apify_results_per_tag))),
            ig_graph_token=env("IG_GRAPH_TOKEN", ""),
            ig_user_id=env("IG_USER_ID", ""),
            ig_graph_version=env("IG_GRAPH_VERSION", cls.ig_graph_version),
            llm_provider=env("LLM_PROVIDER", "auto").lower(),
            llm_base_url=env("LLM_BASE_URL", cls.llm_base_url),
            llm_api_key=env("LLM_API_KEY", ""),
            llm_model=env("LLM_MODEL", cls.llm_model),
            app_token=env("APP_TOKEN", ""),
            db_path=env("DB_PATH", "") or str(data_dir() / "social_climb.db"),
            max_hashtags=int(env("MAX_HASHTAGS", str(cls.max_hashtags))),
        )
        return base.with_saved()

    def with_saved(self) -> "Settings":
        """Overlay settings.json (written by the app) and make sure a phone token exists."""
        settings = self
        if self.settings_path.exists():
            saved = json.loads(self.settings_path.read_text(encoding="utf-8"))
            settings = settings.updated(saved)
            if saved.get("app_token") and not os.environ.get("APP_TOKEN"):
                settings = replace(settings, app_token=saved["app_token"])
        if not settings.app_token:
            settings = replace(settings, app_token=secrets.token_urlsafe(16))
            settings.save()
        return settings
