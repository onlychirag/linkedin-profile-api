class ScraperError(Exception):
    """Base exception for profile scraping failures."""


class InvalidLinkedInUrl(ScraperError):
    """Raised when the input URL is not a LinkedIn profile URL."""


class AuthenticationRequired(ScraperError):
    """Raised when LinkedIn requires a login, MFA, or checkpoint."""


class BrowserUnavailable(ScraperError):
    """Raised when Playwright is not installed or cannot launch Chromium."""

