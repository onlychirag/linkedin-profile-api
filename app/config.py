"""
Application configuration loaded from environment variables.

Required env vars:
  - LI_AT_COOKIE: Your LinkedIn 'li_at' session cookie
Optional env vars:
  - JSESSIONID: Your LinkedIn JSESSIONID cookie (for CSRF token)
  - REQUEST_DELAY_MIN / REQUEST_DELAY_MAX: seconds between requests
  - APP_ENV: 'production' or 'development'
  - LOG_LEVEL: Python logging level string
"""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All configuration is injected via environment variables or .env file."""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # --- LinkedIn Authentication ---
    # How to get this:
    #   1. Log into linkedin.com in Chrome
    #   2. F12 → Application → Cookies → linkedin.com
    #   3. Copy the value of 'li_at'
    LI_AT_COOKIE: str

    # Optional: JSESSIONID cookie, used to derive the CSRF token.
    # Copy from the same cookies panel. Remove surrounding double-quotes.
    JSESSIONID: str = ""

    # --- Rate Limiting ---
    # Random delay (in seconds) between requests to avoid triggering LinkedIn's bot detection.
    REQUEST_DELAY_MIN: float = 2.0
    REQUEST_DELAY_MAX: float = 5.0

    # --- Application ---
    APP_ENV: str = "production"
    LOG_LEVEL: str = "INFO"


# Singleton instance — import this everywhere
settings = Settings()
