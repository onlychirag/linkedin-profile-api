from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.config import Settings
from app.errors import AuthenticationRequired, BrowserUnavailable
from app.models import LinkedInProfile
from app.scraper.parsers import (
    DETAIL_SECTIONS,
    normalize_linkedin_profile_url,
    parse_detail_section_html,
    parse_profile_html,
)
from app.scraper.session import has_persistent_user_data_dir


class DrissionLinkedInScraper:
    """Synchronous DrissionPage backend, run from the async API in a worker thread."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def scrape(self, raw_url: str) -> LinkedInProfile:
        url, _public_identifier = normalize_linkedin_profile_url(raw_url)
        page = self._new_page()
        try:
            authenticated = self._ensure_authenticated(page)
            self._goto(page, url)
            if self._is_auth_wall(page.url, page.html):
                raise AuthenticationRequired(
                    "LinkedIn redirected the DrissionPage browser to login/checkpoint."
                )

            profile = parse_profile_html(page.html, url, resolved_url=page.url)
            profile.extraction.authenticated = authenticated
            profile.extraction.strategies.append("drission-profile-page")
            if has_persistent_user_data_dir(self.settings):
                profile.extraction.strategies.append("persistent-browser-profile")

            for section in DETAIL_SECTIONS:
                detail_url = f"{url.rstrip('/')}/details/{section}/"
                self._goto(page, detail_url)
                if self._is_auth_wall(page.url, page.html):
                    profile.extraction.warnings.append(
                        f"Skipped {section}; LinkedIn redirected to authentication."
                    )
                    continue
                if f"/details/{section}" not in page.url:
                    profile.extraction.warnings.append(
                        f"Skipped {section}; LinkedIn did not serve the detail page."
                    )
                    continue
                items = parse_detail_section_html(page.html, section)
                if items:
                    setattr(profile, section, items)
                    profile.raw_sections[section] = [
                        getattr(item, "source_text", []) for item in items
                    ]
                    profile.extraction.strategies.append(f"drission-{section}")

            return profile
        finally:
            try:
                page.quit(timeout=3, force=True, del_data=False)
            except Exception:
                pass

    def _new_page(self) -> Any:
        try:
            from DrissionPage import ChromiumOptions, ChromiumPage
        except ImportError as exc:
            raise BrowserUnavailable(
                "DrissionPage is not installed. Run `pip install -r requirements.txt`."
            ) from exc

        options = ChromiumOptions()
        browser_path = self.settings.drission_browser_path or self._detect_browser_path()
        if browser_path:
            options.set_browser_path(browser_path)
        if has_persistent_user_data_dir(self.settings):
            options.set_user_data_path(str(self.settings.linkedin_user_data_dir))
        if self.settings.proxy_url:
            options.set_proxy(self.settings.proxy_url)

        options.headless(self.settings.drission_headless)
        options.set_argument("--no-sandbox")
        options.set_argument("--disable-dev-shm-usage")
        options.set_argument("--disable-gpu")
        options.set_argument("--window-size", "1365,900")
        if self.settings.browser_user_agent:
            options.set_argument("--user-agent", self.settings.browser_user_agent)

        try:
            return ChromiumPage(options)
        except Exception as exc:
            raise BrowserUnavailable(
                "DrissionPage could not launch Chromium. Set DRISSION_BROWSER_PATH "
                "to a local Chrome or Edge executable if auto-detection fails."
            ) from exc

    def _ensure_authenticated(self, page: Any) -> bool:
        has_credentials = bool(
            self.settings.linkedin_email and self.settings.linkedin_password
        )
        has_ready_profile = has_persistent_user_data_dir(self.settings)
        if not has_credentials and not has_ready_profile:
            return False

        self._goto(page, "https://www.linkedin.com/feed/")
        if self._page_looks_signed_in(page):
            return True
        if has_ready_profile and self._wait_for_signed_in(page):
            return True
        if not has_credentials:
            return False

        self._goto(page, "https://www.linkedin.com/login")
        username = page.ele("@name=session_key", timeout=10) or page.ele(
            "@id=username", timeout=3
        )
        password = page.ele("@name=session_password", timeout=10) or page.ele(
            "@id=password", timeout=3
        )
        if not username or not password:
            return False
        username.input(self.settings.linkedin_email)
        password.input(self.settings.linkedin_password)

        submit = page.ele("css:button[type='submit']", timeout=5)
        if submit:
            submit.click()

        deadline = time.monotonic() + (self.settings.request_timeout_ms / 1000)
        while time.monotonic() < deadline:
            if self._page_looks_signed_in(page):
                return True
            time.sleep(1)
        raise AuthenticationRequired(
            "LinkedIn login needs MFA/checkpoint or the credentials were rejected."
        )

    def _wait_for_signed_in(self, page: Any) -> bool:
        deadline = time.monotonic() + (self.settings.request_timeout_ms / 1000)
        while time.monotonic() < deadline:
            if self._page_looks_signed_in(page):
                return True
            time.sleep(1)
        return False

    def _goto(self, page: Any, url: str) -> None:
        page.get(url, timeout=self.settings.request_timeout_ms / 1000)
        time.sleep(2)

    @staticmethod
    def _detect_browser_path() -> str | None:
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome",
            "/usr/bin/microsoft-edge",
        ]
        for candidate in candidates:
            if Path(candidate).exists():
                return candidate
        return None

    def _page_looks_signed_in(self, page: Any) -> bool:
        if self._is_auth_wall(page.url, page.html):
            return False
        text = ""
        try:
            body = page.ele("tag:body", timeout=3)
            text = body.text if body else ""
        except Exception:
            pass
        if "Sign in" in text and "Join now" in text:
            return False
        return any(
            marker in text
            for marker in (
                "Start a post",
                "My Network",
                "Messaging",
                "Notifications",
                "View my profile",
            )
        )

    @staticmethod
    def _is_auth_wall(url: str, html: str = "") -> bool:
        lowered = url.lower()
        if any(marker in lowered for marker in ("/login", "/checkpoint", "uas/login", "authwall")):
            return True
        if html and len(html) < 5000 and "authwall" in html:
            return True
        return False
