"""
Tests for the profile API endpoint.

These tests use FastAPI's TestClient to verify:
  - URL validation (rejects bad URLs, accepts good ones)
  - Endpoint returns proper error format on invalid input
  - Health check endpoint works

NOTE: Tests that hit the actual LinkedIn API are marked with comments
and should be run manually (they require valid LI_AT_COOKIE in .env).
"""

import os
import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

# Set a dummy env var so config doesn't fail during testing
os.environ.setdefault("LI_AT_COOKIE", "test_cookie_value")

from app.main import app
from app.schemas import ProfileResponse


client = TestClient(app)


def test_health_check():
    """GET / should return 200 with status ok."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "linkedin-profile-api"


def test_invalid_url_returns_400():
    """Passing a non-LinkedIn URL should return 400."""
    response = client.get("/api/v1/profile", params={"url": "https://google.com"})
    assert response.status_code == 400


def test_missing_url_returns_422():
    """Not providing the url parameter should return 422 (validation error)."""
    response = client.get("/api/v1/profile")
    assert response.status_code == 422


def test_invalid_linkedin_url_company():
    """Company URLs should be rejected — we only accept /in/ profile URLs."""
    response = client.get(
        "/api/v1/profile",
        params={"url": "https://www.linkedin.com/company/google"},
    )
    assert response.status_code == 400


def test_valid_url_format_accepted():
    """A valid LinkedIn URL format should pass validation (scraping may fail without real cookie)."""
    with patch(
        "app.routes.profile.orchestrator.get_profile",
        new_callable=AsyncMock,
        return_value=ProfileResponse(
            profile_url="https://www.linkedin.com/in/test-user",
            first_name="Test",
            last_name="User",
            full_name="Test User",
            source="voyager",
        ),
    ):
        response = client.get(
            "/api/v1/profile",
            params={"url": "https://www.linkedin.com/in/test-user"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["full_name"] == "Test User"


def test_openapi_docs_accessible():
    """Swagger docs should be available at /docs."""
    response = client.get("/docs")
    assert response.status_code == 200
