from fastapi.testclient import TestClient
from fastapi.responses import Response

from app.config import Settings
import app.main as main_module
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


def test_profile_endpoint_proxies_to_upstream_when_configured(monkeypatch) -> None:
    settings = Settings(
        api_key=None,
        upstream_api_base_url="https://oracle.example",
        upstream_api_key="oracle-secret",
    )
    calls = {}

    async def fake_proxy_profile(
        settings_arg,
        method,
        path,
        params=None,
        json=None,
    ) -> LinkedInProfile:
        calls.update(
            {
                "settings": settings_arg,
                "method": method,
                "path": path,
                "params": params,
                "json": json,
            }
        )
        return LinkedInProfile(
            profile_url="https://www.linkedin.com/in/jane-doe/",
            public_identifier="jane-doe",
            name="Jane Doe",
            extraction=ExtractionMetadata(
                requested_url="https://www.linkedin.com/in/jane-doe/",
                resolved_url="https://www.linkedin.com/in/jane-doe/",
                public_identifier="jane-doe",
                strategies=["upstream"],
            ),
        )

    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    monkeypatch.setattr(main_module, "_proxy_upstream_profile", fake_proxy_profile)
    test_app = main_module.create_app()
    client = TestClient(test_app)

    response = client.get(
        "/api/profile",
        params={"url": "https://www.linkedin.com/in/jane-doe/"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Jane Doe"
    assert calls["settings"] is settings
    assert calls["method"] == "GET"
    assert calls["path"] == "/api/profile"
    assert calls["params"] == {"url": "https://www.linkedin.com/in/jane-doe/"}


def test_image_endpoint_proxies_to_upstream_when_configured(monkeypatch) -> None:
    settings = Settings(
        api_key=None,
        upstream_api_base_url="https://oracle.example",
        upstream_api_key="oracle-secret",
    )
    calls = {}

    async def fake_proxy_image(settings_arg, image_url: str) -> Response:
        calls["settings"] = settings_arg
        calls["image_url"] = image_url
        return Response(content=b"image-data", media_type="image/jpeg")

    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    monkeypatch.setattr(main_module, "_proxy_upstream_image", fake_proxy_image)
    test_app = main_module.create_app()
    client = TestClient(test_app)

    response = client.get(
        "/api/image",
        params={"url": "https://media.licdn.com/dms/image/test.jpg"},
    )

    assert response.status_code == 200
    assert response.content == b"image-data"
    assert response.headers["content-type"] == "image/jpeg"
    assert calls["settings"] is settings
    assert calls["image_url"] == "https://media.licdn.com/dms/image/test.jpg"
