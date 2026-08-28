from fastapi.testclient import TestClient

from app.main import app, get_scraper
from app.models import ExtractionMetadata, LinkedInProfile


class FakeScraper:
    async def scrape(self, url: str) -> LinkedInProfile:
        return LinkedInProfile(
            profile_url="https://www.linkedin.com/in/jane-doe/",
            public_identifier="jane-doe",
            name="Jane Doe",
            headline="Staff Engineer",
            extraction=ExtractionMetadata(
                requested_url=url,
                resolved_url="https://www.linkedin.com/in/jane-doe/",
                public_identifier="jane-doe",
                strategies=["fake"],
            ),
        )


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_endpoint_serves_main_page() -> None:
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "LinkedIn profile data" in response.text
    assert "Founder Radar" in response.text
    assert "Meet Shah" in response.text
    assert "Padam Kataria" in response.text
    assert "Profile Lookup" in response.text


def test_ui_endpoint_serves_form() -> None:
    client = TestClient(app)
    response = client.get("/ui")

    assert response.status_code == 200
    assert "LinkedIn profile URL" in response.text
    assert "/api/profile" in response.text


def test_profile_endpoint_uses_scraper_dependency() -> None:
    app.dependency_overrides[get_scraper] = lambda: FakeScraper()
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/profiles",
            json={"url": "https://www.linkedin.com/in/jane-doe/"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["name"] == "Jane Doe"


def test_profile_compat_endpoint_uses_scraper_dependency() -> None:
    app.dependency_overrides[get_scraper] = lambda: FakeScraper()
    client = TestClient(app)

    try:
        response = client.get(
            "/api/profile",
            params={"url": "https://www.linkedin.com/in/jane-doe/"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["name"] == "Jane Doe"
