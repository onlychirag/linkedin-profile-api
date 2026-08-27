"""
Shared parsing and cleaning utilities used by both the Voyager client
and the Playwright browser scraper.
"""

from __future__ import annotations

import calendar
import re
from urllib.parse import urlparse


def extract_public_id(url: str) -> str:
    """
    Extract the public profile identifier from a LinkedIn URL.

    Examples:
        'https://www.linkedin.com/in/john-doe-123/'  → 'john-doe-123'
        'https://linkedin.com/in/jane-smith?param=1'  → 'jane-smith'

    Raises:
        ValueError: If the URL doesn't contain '/in/<id>'.
    """
    # Strip trailing slashes and query params for clean parsing
    url = url.rstrip("/")
    parts = url.split("/in/")
    if len(parts) < 2:
        raise ValueError(f"Cannot extract public ID from URL: {url}")
    # Take only the ID portion, strip query params and hash fragments
    public_id = parts[1].split("/")[0].split("?")[0].split("#")[0]
    if not public_id:
        raise ValueError(f"Empty public ID extracted from URL: {url}")
    return public_id


def format_voyager_date(date_obj: dict | None) -> str | None:
    """
    Convert a Voyager date object to a human-readable string.

    Voyager dates look like: {"month": 1, "year": 2020}
    We convert to: "Jan 2020"

    If only year is present, returns just the year as a string.
    Returns None if date_obj is falsy or has no year.
    """
    if not date_obj or not isinstance(date_obj, dict):
        return None
    month = date_obj.get("month")
    year = date_obj.get("year")
    if month and year:
        try:
            return f"{calendar.month_abbr[int(month)]} {year}"
        except (IndexError, ValueError):
            return str(year)
    return str(year) if year else None


def clean_text(text: str | None) -> str | None:
    """
    Clean scraped text by collapsing whitespace and stripping.
    Returns None if input is None or becomes empty after cleaning.
    """
    if not text:
        return None
    # Collapse multiple whitespace chars (including newlines) into single spaces
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned if cleaned else None


def is_valid_linkedin_url(url: str) -> bool:
    """
    Check whether a URL looks like a valid LinkedIn profile URL.

    Accepts:
      - https://www.linkedin.com/in/username
      - https://linkedin.com/in/username
      - http://www.linkedin.com/in/username  (will be upgraded to HTTPS)

    Rejects everything else.
    """
    pattern = r"^https?://(www\.)?linkedin\.com/in/[\w\-]+(/)?(\?.*)?$"
    return bool(re.match(pattern, url))


def normalize_linkedin_url(url: str) -> str:
    """
    Normalize a LinkedIn URL to a canonical form:
      - Ensure HTTPS
      - Remove trailing slashes
      - Remove query parameters

    Returns the cleaned URL.
    """
    url = url.strip()
    if url.startswith("http://"):
        url = url.replace("http://", "https://", 1)
    # Remove query params and fragments
    parsed = urlparse(url)
    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return clean_url.rstrip("/")
