from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.errors import AuthenticationRequired, BrowserUnavailable, ScraperError
from app.models import LinkedInProfile
from app.scraper.parsers import (
    DETAIL_SECTIONS,
    merge_profiles,
    normalize_linkedin_profile_url,
    parse_detail_section_html,
    parse_profile_html,
    profile_has_core_data,
)
from app.scraper.session import (
    has_persistent_user_data_dir,
    load_storage_state,
    save_storage_state,
)


class LinkedInScraper:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def scrape(self, raw_url: str) -> LinkedInProfile:
        url, _public_identifier = normalize_linkedin_profile_url(raw_url)
        public_profile = await self._scrape_public_html(url)

        if not self.settings.enable_browser_scraper:
            if profile_has_core_data(public_profile):
                return public_profile
            raise ScraperError("Public profile metadata was not available")

        browser_profile: LinkedInProfile | None = None
        warnings: list[str] = []
        for backend in self._backend_order():
            try:
                if backend == "drission":
                    browser_profile = await self._scrape_with_drission(url)
                else:
                    browser_profile = await self._scrape_with_browser(url)
                break
            except BrowserUnavailable as exc:
                warnings.append(str(exc))
                continue
            except AuthenticationRequired as exc:
                warnings.append(str(exc))
                if self.settings.browser_backend in {"playwright", "drission"}:
                    raise
            except Exception as exc:
                warnings.append(f"{backend} scrape failed: {exc}")
                if self.settings.browser_backend in {"playwright", "drission"}:
                    raise ScraperError(f"Unable to extract profile: {exc}") from exc

        public_profile.extraction.warnings.extend(warnings)
        if browser_profile is None:
            if profile_has_core_data(public_profile):
                return public_profile
            if warnings:
                raise ScraperError("; ".join(warnings))
            raise ScraperError("Unable to extract profile")

        return merge_profiles(browser_profile, public_profile)

    def _backend_order(self) -> list[str]:
        backend = self.settings.browser_backend
        if backend == "playwright":
            return ["playwright"]
        if backend == "drission":
            return ["drission"]
        order: list[str] = []
        if has_persistent_user_data_dir(self.settings):
            order.append("playwright")
        if self.settings.enable_drission_scraper:
            order.append("drission")
        if "playwright" not in order:
            order.append("playwright")
        return order

    async def _scrape_with_drission(self, url: str) -> LinkedInProfile:
        from app.scraper.drission import DrissionLinkedInScraper

        scraper = DrissionLinkedInScraper(self.settings)
        return await asyncio.to_thread(scraper.scrape, url)

    async def _scrape_public_html(self, url: str) -> LinkedInProfile:
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": self.settings.user_agent,
        }
        try:
            async with httpx.AsyncClient(
                headers=headers,
                follow_redirects=True,
                timeout=self.settings.request_timeout_ms / 1000,
            ) as client:
                response = await client.get(url)
                profile = parse_profile_html(
                    response.text, url, resolved_url=str(response.url)
                )
                if response.status_code >= 400:
                    profile.extraction.warnings.append(
                        f"Public fetch returned HTTP {response.status_code}"
                    )
                return profile
        except Exception as exc:
            profile = parse_profile_html("", url)
            profile.extraction.warnings.append(f"Public fetch failed: {exc}")
            return profile

    async def _scrape_with_browser(self, url: str) -> LinkedInProfile:
        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise BrowserUnavailable(
                "Playwright is not installed. Run `pip install -r requirements.txt`."
            ) from exc

        async with async_playwright() as playwright:
            browser = None
            context = None
            use_persistent_profile = has_persistent_user_data_dir(self.settings)
            try:
                if use_persistent_profile:
                    context = await playwright.chromium.launch_persistent_context(
                        user_data_dir=str(self.settings.linkedin_user_data_dir),
                        headless=self.settings.playwright_headless,
                        args=["--no-sandbox", "--disable-dev-shm-usage"],
                        viewport={"width": 1365, "height": 900},
                        locale="en-US",
                    )
                    if self.settings.browser_user_agent:
                        await context.set_extra_http_headers(
                            {"User-Agent": self.settings.browser_user_agent}
                        )
                else:
                    browser = await playwright.chromium.launch(
                        headless=self.settings.playwright_headless,
                        args=["--no-sandbox", "--disable-dev-shm-usage"],
                    )
                    context_args: dict[str, Any] = {
                        "viewport": {"width": 1365, "height": 900},
                        "locale": "en-US",
                    }
                    if self.settings.browser_user_agent:
                        context_args["user_agent"] = self.settings.browser_user_agent
                    storage_state = load_storage_state(self.settings)
                    if storage_state:
                        context_args["storage_state"] = storage_state
                    context = await browser.new_context(**context_args)
            except Exception as exc:
                raise BrowserUnavailable(
                    "Chromium could not launch. Run `python -m playwright install chromium`."
                ) from exc
            try:
                page = context.pages[0] if context.pages else await context.new_page()
                authenticated = await self._ensure_authenticated(context, page)
                await self._goto(page, url, PlaywrightTimeoutError)
                if self._is_auth_wall(page.url):
                    if not authenticated:
                        raise AuthenticationRequired(
                            "LinkedIn requires authentication. Set LINKEDIN_EMAIL/LINKEDIN_PASSWORD "
                            "or create a Playwright storage state with scripts/create_linkedin_session.py."
                        )
                    raise AuthenticationRequired(
                        "LinkedIn sent the session to a login or checkpoint page."
                    )

                await self._expand_visible_sections(page)
                html = await page.content()
                profile = parse_profile_html(html, url, resolved_url=page.url)
                profile.extraction.authenticated = authenticated
                profile.extraction.strategies.append("playwright-profile-page")
                if use_persistent_profile:
                    profile.extraction.strategies.append("persistent-browser-profile")

                for section in DETAIL_SECTIONS:
                    detail_url = f"{url.rstrip('/')}/details/{section}/"
                    await self._goto(page, detail_url, PlaywrightTimeoutError)
                    if self._is_auth_wall(page.url):
                        profile.extraction.warnings.append(
                            f"Skipped {section}; LinkedIn redirected to authentication."
                        )
                        continue
                    if f"/details/{section}" not in page.url:
                        profile.extraction.warnings.append(
                            f"Skipped {section}; LinkedIn did not serve the detail page."
                        )
                        continue
                    await self._expand_visible_sections(page)
                    detail_html = await page.content()
                    items = parse_detail_section_html(detail_html, section)
                    if items:
                        setattr(profile, section, items)
                        profile.raw_sections[section] = [
                            getattr(item, "source_text", []) for item in items
                        ]
                        profile.extraction.strategies.append(f"playwright-{section}")

                await save_storage_state(context, self.settings)
                return profile
            finally:
                if context:
                    await context.close()
                if browser:
                    await browser.close()

    async def _ensure_authenticated(self, context: Any, page: Any | None = None) -> bool:
        has_credentials = bool(self.settings.linkedin_email and self.settings.linkedin_password)
        has_state = bool(
            load_storage_state(self.settings) or has_persistent_user_data_dir(self.settings)
        )
        if not has_credentials and not has_state:
            return False

        owns_page = page is None
        if page is None:
            page = await context.new_page()
        try:
            await page.goto(
                "https://www.linkedin.com/feed/",
                wait_until="domcontentloaded",
                timeout=self.settings.request_timeout_ms,
            )
            if await self._page_looks_signed_in(page):
                return True
            if has_state and await self._wait_for_signed_in(page):
                return True
            if not has_credentials:
                return False

            await page.goto(
                "https://www.linkedin.com/login",
                wait_until="domcontentloaded",
                timeout=self.settings.request_timeout_ms,
            )
            await page.fill("input[name='session_key']", self.settings.linkedin_email)
            await page.fill("input[name='session_password']", self.settings.linkedin_password)
            await page.click("button[type='submit']")
            await page.wait_for_load_state("domcontentloaded", timeout=self.settings.request_timeout_ms)

            if not await self._wait_for_signed_in(page):
                raise AuthenticationRequired(
                    "LinkedIn login needs MFA/checkpoint or the credentials were rejected."
                )
            await save_storage_state(context, self.settings)
            return True
        finally:
            if owns_page:
                await page.close()

    async def _wait_for_signed_in(self, page: Any) -> bool:
        deadline = asyncio.get_running_loop().time() + (
            self.settings.request_timeout_ms / 1000
        )
        while asyncio.get_running_loop().time() < deadline:
            if await self._page_looks_signed_in(page):
                return True
            await page.wait_for_timeout(1000)
        return False

    async def _page_looks_signed_in(self, page: Any) -> bool:
        if self._is_auth_wall(page.url):
            return False
        try:
            text = await page.locator("body").inner_text(timeout=3000)
        except Exception:
            text = ""
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

    async def _goto(self, page: Any, url: str, timeout_error: type[Exception]) -> None:
        await page.goto(
            url, wait_until="domcontentloaded", timeout=self.settings.request_timeout_ms
        )
        try:
            await page.wait_for_load_state("networkidle", timeout=5_000)
        except timeout_error:
            pass

    async def _expand_visible_sections(self, page: Any) -> None:
        labels = [
            re.compile(r"see more", re.IGNORECASE),
            re.compile(r"show more", re.IGNORECASE),
            re.compile(r"show all", re.IGNORECASE),
        ]
        for label in labels:
            buttons = page.get_by_role("button", name=label)
            try:
                count = min(await buttons.count(), 10)
            except Exception:
                continue
            for index in range(count):
                try:
                    await buttons.nth(index).click(timeout=750)
                    await page.wait_for_timeout(250)
                except Exception:
                    continue

    @staticmethod
    def _is_auth_wall(url: str) -> bool:
        lowered = url.lower()
        return any(
            marker in lowered
            for marker in ("/login", "/checkpoint", "uas/login", "authwall")
        )
