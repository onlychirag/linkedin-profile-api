from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.errors import AuthenticationRequired, InvalidLinkedInUrl, ScraperError
from app.models import LinkedInProfile
from app.scraper.linkedin import LinkedInScraper
from app.scraper.session import has_persistent_user_data_dir


class ProfileRequest(BaseModel):
    url: str = Field(..., examples=["https://www.linkedin.com/in/example/"])


@lru_cache(maxsize=1)
def get_scraper() -> LinkedInScraper:
    return LinkedInScraper(get_settings())


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="Hosted API that extracts structured data from LinkedIn profile URLs.",
        version="1.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": settings.app_name, "docs": "/docs", "health": "/health"}

    @app.get("/health")
    async def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "browser_backend": settings.browser_backend,
            "browser_scraper_enabled": settings.enable_browser_scraper,
            "auth_http_scraper_enabled": settings.enable_auth_http_scraper,
            "drission_scraper_enabled": settings.enable_drission_scraper,
            "linkedin_credentials_configured": bool(
                settings.linkedin_email and settings.linkedin_password
            ),
            "storage_state_configured": bool(
                settings.linkedin_storage_state_b64
                or settings.linkedin_storage_state_path.exists()
                or has_persistent_user_data_dir(settings)
            ),
        }

    @app.post("/api/v1/profiles", response_model=LinkedInProfile)
    async def scrape_profile_post(
        payload: ProfileRequest,
        _: None = Depends(require_api_key),
        scraper: LinkedInScraper = Depends(get_scraper),
    ) -> LinkedInProfile:
        return await _scrape(payload.url, scraper)

    @app.get("/api/v1/profiles", response_model=LinkedInProfile)
    async def scrape_profile_get(
        url: str = Query(..., description="LinkedIn /in/ or /pub/ profile URL"),
        _: None = Depends(require_api_key),
        scraper: LinkedInScraper = Depends(get_scraper),
    ) -> LinkedInProfile:
        return await _scrape(url, scraper)

    @app.get("/api/profile", response_model=LinkedInProfile)
    async def scrape_profile_compat_get(
        url: str = Query(..., description="LinkedIn /in/ or /pub/ profile URL"),
        _: None = Depends(require_api_key),
        scraper: LinkedInScraper = Depends(get_scraper),
    ) -> LinkedInProfile:
        return await _scrape(url, scraper)

    return app


async def require_api_key(
    request: Request, x_api_key: str | None = Header(default=None)
) -> None:
    settings = get_settings()
    if not settings.api_key:
        return
    provided = x_api_key or request.query_params.get("api_key")
    if provided != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
        )


async def _scrape(url: str, scraper: LinkedInScraper) -> LinkedInProfile:
    try:
        return await scraper.scrape(url)
    except InvalidLinkedInUrl as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AuthenticationRequired as exc:
        raise HTTPException(status_code=424, detail=str(exc)) from exc
    except ScraperError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


app = create_app()
