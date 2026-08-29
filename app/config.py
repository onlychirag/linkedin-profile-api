from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return default
    values = [part.strip() for part in raw.split(",") if part.strip()]
    return values or default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "LinkedIn Profile API")
    api_key: str | None = os.getenv("API_KEY") or None
    allowed_origins: list[str] = None  # type: ignore[assignment]

    enable_browser_scraper: bool = _bool_env("ENABLE_BROWSER_SCRAPER", False)
    enable_auth_http_scraper: bool = _bool_env("ENABLE_AUTH_HTTP_SCRAPER", True)
    enable_drission_scraper: bool = _bool_env("ENABLE_DRISSION_SCRAPER", True)
    browser_backend: str = os.getenv("BROWSER_BACKEND", "auto").strip().lower()
    playwright_headless: bool = _bool_env("PLAYWRIGHT_HEADLESS", True)
    drission_headless: bool = _bool_env("DRISSION_HEADLESS", True)
    request_timeout_ms: int = _int_env("REQUEST_TIMEOUT_MS", 45_000)

    linkedin_email: str | None = (
        os.getenv("LINKEDIN_EMAIL") or os.getenv("LINKEDIN_USERNAME") or None
    )
    linkedin_password: str | None = os.getenv("LINKEDIN_PASSWORD") or None
    proxy_url: str | None = os.getenv("PROXY_URL") or None
    upstream_api_base_url: str | None = os.getenv("UPSTREAM_API_BASE_URL") or None
    upstream_api_key: str | None = os.getenv("UPSTREAM_API_KEY") or None
    linkedin_user_data_dir: Path = Path(
        os.getenv("LINKEDIN_USER_DATA_DIR", ".auth/linkedin-browser-profile")
    )
    linkedin_storage_state_path: Path = Path(
        os.getenv("LINKEDIN_STORAGE_STATE_PATH", ".auth/linkedin-state.json")
    )
    linkedin_storage_state_b64: str | None = (
        os.getenv("LINKEDIN_STORAGE_STATE_B64") or None
    )
    drission_browser_path: str | None = os.getenv("DRISSION_BROWSER_PATH") or None

    user_agent: str = os.getenv(
        "SCRAPER_USER_AGENT",
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    browser_user_agent: str | None = os.getenv("BROWSER_USER_AGENT") or None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "allowed_origins", _csv_env("ALLOWED_ORIGINS", ["*"])
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
