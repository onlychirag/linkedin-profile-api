"""
Playwright Browser Scraper — Fallback scraping strategy.

This module uses a headless Chromium browser to navigate to a LinkedIn profile
page, render it, and extract data from the DOM. It is slower than the Voyager
API client but more resilient when Voyager endpoints change or cookies expire.

HOW IT WORKS:
  1. Launch headless Chromium with a realistic User-Agent.
  2. Inject the li_at cookie for authentication.
  3. Navigate to the profile URL and wait for the page to fully load.
  4. Scroll down the page to trigger lazy-loaded sections (experience, education, etc.)
  5. Use page.evaluate() to run JavaScript in the page context and extract text.
  6. Map the extracted text to our Pydantic schemas.

IMPORTANT CSS SELECTORS (may break when LinkedIn updates their UI):
  - Name:       h1 (the first h1 on the profile page)
  - Headline:   .text-body-medium.break-words
  - Location:   .text-body-small.inline.t-black--light.break-words
  - About:      #about ~ div .inline-show-more-text
  - Photo:      img.pv-top-card-profile-picture__image--show
  - Experience: #experience section li elements
  - Education:  #education section li elements
"""

from __future__ import annotations

import logging

from playwright.async_api import async_playwright

from app.config import settings
from app.schemas import (
    Education,
    Experience,
    ProfileResponse,
)
from app.utils.parsing import clean_text

logger = logging.getLogger(__name__)


class BrowserScraper:
    """
    Async scraper that uses Playwright to render LinkedIn profile pages
    and extract data from the DOM.

    Usage:
        scraper = BrowserScraper()
        profile = await scraper.get_profile("https://www.linkedin.com/in/john-doe")
    """

    async def get_profile(self, profile_url: str) -> ProfileResponse:
        """
        Scrape a LinkedIn profile using a headless browser.

        Args:
            profile_url: Full LinkedIn profile URL.

        Returns:
            ProfileResponse with data extracted from the page DOM.

        Raises:
            playwright.async_api.Error: On navigation failures or timeouts.
        """
        logger.info(f"Browser: launching headless Chromium for {profile_url}")

        async with async_playwright() as p:
            # Launch in headless mode — no visible browser window
            browser = await p.chromium.launch(headless=True)

            # Create a browser context with a realistic user-agent.
            # The context holds cookies and other session state.
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )

            # Inject the li_at authentication cookie.
            # This is the same cookie you'd have in your browser after logging in.
            await context.add_cookies(
                [
                    {
                        "name": "li_at",
                        "value": settings.LI_AT_COOKIE,
                        "domain": ".linkedin.com",
                        "path": "/",
                    }
                ]
            )

            page = await context.new_page()

            # Navigate to the profile page.
            # 'networkidle' waits until there are no more than 0 network connections
            # for at least 500ms — ensures the page is "done" loading.
            await page.goto(
                profile_url, wait_until="networkidle", timeout=45000
            )

            # Extra wait for JavaScript-rendered content
            await page.wait_for_timeout(3000)

            # Scroll down the page to trigger lazy loading of sections
            # (experience, education, skills, etc. load on scroll)
            for i in range(6):
                await page.evaluate("window.scrollBy(0, 800)")
                await page.wait_for_timeout(1000)

            # Scroll back to top to ensure profile header is in viewport
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(500)

            # Extract all data in ONE page.evaluate call to minimize round-trips.
            # This JavaScript runs inside the browser page context.
            data = await page.evaluate(
                """() => {
                // Helper: get text from first element matching selector
                const getText = (sel) => {
                    const el = document.querySelector(sel);
                    return el ? el.innerText.trim() : null;
                };

                // Helper: get all text values from elements matching selector
                const getAllText = (sel) => {
                    return Array.from(document.querySelectorAll(sel))
                        .map(el => el.innerText.trim())
                        .filter(Boolean);
                };

                // Helper: get image src
                const getImgSrc = (sel) => {
                    const el = document.querySelector(sel);
                    return el ? el.src : null;
                };

                // --- Extract basic profile info ---
                const name = getText('h1');
                const headline = getText('.text-body-medium.break-words');
                const location = getText('.text-body-small.inline.t-black--light.break-words');

                // --- About section ---
                // LinkedIn wraps "About" text in an expandable container
                const about = getText('#about ~ div .inline-show-more-text')
                    || getText('#about + div + div .inline-show-more-text')
                    || getText('[class*="about"] .inline-show-more-text');

                // --- Profile image ---
                const profileImage = getImgSrc('img.pv-top-card-profile-picture__image--show')
                    || getImgSrc('img.profile-photo-edit__preview')
                    || getImgSrc('.pv-top-card__photo img');

                // --- Experience section ---
                const experiences = [];
                const expSection = document.querySelector('#experience');
                if (expSection) {
                    const expParent = expSection.closest('section');
                    if (expParent) {
                        const items = expParent.querySelectorAll(':scope > div > div > ul > li');
                        items.forEach(li => {
                            const spans = li.querySelectorAll('span[aria-hidden="true"]');
                            const texts = Array.from(spans).map(s => s.innerText.trim());
                            if (texts.length >= 2) {
                                experiences.push({
                                    title: texts[0] || null,
                                    company: texts[1] || null,
                                    duration: texts[2] || null,
                                    location: texts[3] || null,
                                });
                            }
                        });
                    }
                }

                // --- Education section ---
                const educations = [];
                const eduSection = document.querySelector('#education');
                if (eduSection) {
                    const eduParent = eduSection.closest('section');
                    if (eduParent) {
                        const items = eduParent.querySelectorAll(':scope > div > div > ul > li');
                        items.forEach(li => {
                            const spans = li.querySelectorAll('span[aria-hidden="true"]');
                            const texts = Array.from(spans).map(s => s.innerText.trim());
                            if (texts.length >= 1) {
                                educations.push({
                                    school: texts[0] || null,
                                    degree: texts[1] || null,
                                    years: texts[2] || null,
                                });
                            }
                        });
                    }
                }

                // --- Skills section ---
                const skills = [];
                const skillSection = document.querySelector('#skills');
                if (skillSection) {
                    const skillParent = skillSection.closest('section');
                    if (skillParent) {
                        const items = skillParent.querySelectorAll('span[aria-hidden="true"]');
                        items.forEach(span => {
                            const text = span.innerText.trim();
                            // Filter out endorsement counts and other non-skill text
                            if (text && !text.match(/^\\d+$/) && text.length < 100) {
                                skills.push(text);
                            }
                        });
                    }
                }

                return {
                    name,
                    headline,
                    location,
                    about,
                    profileImage,
                    experiences,
                    educations,
                    skills,
                };
            }"""
            )

            await browser.close()

        # --- Map extracted data to our Pydantic models ---
        name = data.get("name") or ""
        name_parts = name.split(" ", 1)

        experiences = [
            Experience(
                title=exp.get("title"),
                company=exp.get("company"),
                duration=exp.get("duration"),
                location=exp.get("location"),
            )
            for exp in (data.get("experiences") or [])
        ]

        educations = [
            Education(
                school=edu.get("school"),
                degree=edu.get("degree"),
            )
            for edu in (data.get("educations") or [])
        ]

        skills = data.get("skills") or []

        return ProfileResponse(
            profile_url=profile_url,
            first_name=name_parts[0] if name_parts else None,
            last_name=name_parts[1] if len(name_parts) > 1 else None,
            full_name=clean_text(name) or None,
            headline=clean_text(data.get("headline")),
            location=clean_text(data.get("location")),
            about=clean_text(data.get("about")),
            profile_image_url=data.get("profileImage"),
            experience=experiences,
            education=educations,
            skills=skills,
            source="browser",
        )
