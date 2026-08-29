import pytest

from app.config import Settings
from app.models import (
    ExperienceItem,
    ExtractionMetadata,
    LinkedInProfile,
    SkillItem,
)
from app.scraper.linkedin import LinkedInScraper


PROFILE_URL = "https://www.linkedin.com/in/jane-doe/"


def _profile(
    *,
    strategies: list[str],
    authenticated: bool = False,
    experience: list[ExperienceItem] | None = None,
    skills: list[SkillItem] | None = None,
) -> LinkedInProfile:
    return LinkedInProfile(
        profile_url=PROFILE_URL,
        public_identifier="jane-doe",
        name="Jane Doe",
        experience=experience or [],
        skills=skills or [],
        extraction=ExtractionMetadata(
            requested_url=PROFILE_URL,
            resolved_url=PROFILE_URL,
            public_identifier="jane-doe",
            authenticated=authenticated,
            strategies=strategies,
        ),
    )


@pytest.mark.asyncio
async def test_browser_scraper_enriches_authenticated_http_result(monkeypatch) -> None:
    settings = Settings(
        enable_auth_http_scraper=True,
        enable_browser_scraper=True,
        browser_backend="playwright",
    )
    scraper = LinkedInScraper(settings)
    calls: list[str] = []

    async def fake_public_scrape(url: str) -> LinkedInProfile:
        calls.append("public")
        return _profile(strategies=["public-metadata"])

    async def fake_authenticated_http_scrape(url: str) -> LinkedInProfile:
        calls.append("authenticated-http")
        return _profile(
            authenticated=True,
            strategies=["authenticated-http-profile", "authenticated-http-experience"],
            experience=[ExperienceItem(title="Engineer", company="Example Co")],
        )

    async def fake_browser_scrape(url: str) -> LinkedInProfile:
        calls.append("browser")
        return _profile(
            authenticated=True,
            strategies=["playwright-profile-page", "playwright-skills"],
            skills=[SkillItem(name="Python")],
        )

    monkeypatch.setattr(scraper, "_scrape_public_html", fake_public_scrape)
    monkeypatch.setattr(
        scraper, "_scrape_authenticated_http", fake_authenticated_http_scrape
    )
    monkeypatch.setattr(scraper, "_scrape_with_browser", fake_browser_scrape)

    profile = await scraper.scrape(PROFILE_URL)

    assert calls == ["public", "authenticated-http", "browser"]
    assert profile.experience[0].company == "Example Co"
    assert profile.skills[0].name == "Python"
    assert "authenticated-http-experience" in profile.extraction.strategies
    assert "playwright-skills" in profile.extraction.strategies
