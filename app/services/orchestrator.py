"""
Profile Orchestrator — Waterfall strategy router.

This module implements the dual-strategy pattern:
  1. Try the Voyager API client first (fast, structured data).
  2. If Voyager fails for ANY reason (expired cookie, endpoint change, rate limit),
     fall back to the Playwright browser scraper.
  3. If both fail, raise a RuntimeError with details from both failures.

This pattern ensures maximum resilience — the API stays functional even when
LinkedIn changes their internal API, as long as the page HTML still renders.
"""

from __future__ import annotations

import logging

from app.schemas import ProfileResponse
from app.services.browser import BrowserScraper
from app.services.voyager import VoyagerClient

logger = logging.getLogger(__name__)


class ProfileOrchestrator:
    """
    Routes profile requests through the strategy waterfall.

    Usage:
        orchestrator = ProfileOrchestrator()
        result = await orchestrator.get_profile("https://www.linkedin.com/in/john-doe")
    """

    def __init__(self) -> None:
        self.voyager = VoyagerClient()
        self.browser = BrowserScraper()

    async def get_profile(self, profile_url: str) -> ProfileResponse:
        """
        Attempt to scrape a LinkedIn profile using the waterfall strategy.

        Strategy order:
          1. Voyager API (fast, clean JSON)
          2. Playwright browser (slower, DOM scraping)

        Args:
            profile_url: Full LinkedIn profile URL.

        Returns:
            ProfileResponse from whichever strategy succeeds first.

        Raises:
            RuntimeError: If ALL strategies fail.
        """
        errors: list[str] = []

        # ──────────────────────────────────────────────
        # Strategy 1: Voyager API (primary)
        # ──────────────────────────────────────────────
        try:
            logger.info(f"[1/2] Trying Voyager API for: {profile_url}")
            result = await self.voyager.get_profile(profile_url)
            logger.info("[1/2] Voyager API succeeded ✓")
            return result
        except Exception as e:
            error_msg = f"Voyager failed: {type(e).__name__}: {e}"
            logger.warning(f"[1/2] {error_msg}")
            errors.append(error_msg)

        # ──────────────────────────────────────────────
        # Strategy 2: Playwright browser (fallback)
        # ──────────────────────────────────────────────
        try:
            logger.info(f"[2/2] Falling back to browser scraper for: {profile_url}")
            result = await self.browser.get_profile(profile_url)
            logger.info("[2/2] Browser scraper succeeded ✓")
            return result
        except Exception as e:
            error_msg = f"Browser failed: {type(e).__name__}: {e}"
            logger.error(f"[2/2] {error_msg}")
            errors.append(error_msg)

        # ──────────────────────────────────────────────
        # All strategies exhausted
        # ──────────────────────────────────────────────
        combined = " | ".join(errors)
        raise RuntimeError(f"All scraping strategies failed. Errors: {combined}")
