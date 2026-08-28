from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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
        return {
            "service": settings.app_name,
            "ui": "/ui",
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/ui", response_class=HTMLResponse)
    async def ui() -> str:
        return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LinkedIn Profile API</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #596579;
      --line: #d8dde6;
      --accent: #0a66c2;
      --accent-dark: #084f96;
      --danger: #b42318;
      --code: #111827;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    main {
      width: min(1120px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 32px 0;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 20px;
    }
    h1 {
      margin: 0;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: 0;
    }
    a {
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }
    .workspace {
      display: grid;
      grid-template-columns: minmax(280px, 420px) minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }
    label {
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }
    input {
      width: 100%;
      min-height: 44px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 12px;
      font: inherit;
      color: var(--ink);
      background: transparent;
    }
    button {
      width: 100%;
      min-height: 44px;
      margin-top: 12px;
      border: 0;
      border-radius: 6px;
      background: var(--accent);
      color: white;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }
    button:hover { background: var(--accent-dark); }
    button:disabled {
      cursor: progress;
      opacity: 0.72;
    }
    .status {
      min-height: 22px;
      margin-top: 12px;
      color: var(--muted);
      font-size: 14px;
      overflow-wrap: anywhere;
    }
    .error { color: var(--danger); }
    pre {
      min-height: 420px;
      max-height: calc(100vh - 160px);
      margin: 0;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
      color: #dbeafe;
      background: var(--code);
      border-radius: 6px;
      padding: 16px;
      font: 13px/1.55 ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
    }
    @media (max-width: 760px) {
      main { width: min(100vw - 24px, 680px); padding: 20px 0; }
      header { align-items: flex-start; flex-direction: column; }
      .workspace { grid-template-columns: 1fr; }
      pre { min-height: 320px; max-height: none; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>LinkedIn Profile API</h1>
      <a href="/docs">Swagger Docs</a>
    </header>
    <div class="workspace">
      <section>
        <form id="scrape-form">
          <label for="profile-url">LinkedIn profile URL</label>
          <input
            id="profile-url"
            name="profile-url"
            type="url"
            value="https://www.linkedin.com/in/chirag-kakwani-8b4055284/"
            autocomplete="url"
            required
          >
          <button id="submit-button" type="submit">Scrape</button>
          <div id="status" class="status"></div>
        </form>
      </section>
      <section>
        <pre id="output">{}</pre>
      </section>
    </div>
  </main>
  <script>
    const form = document.querySelector("#scrape-form");
    const input = document.querySelector("#profile-url");
    const output = document.querySelector("#output");
    const status = document.querySelector("#status");
    const button = document.querySelector("#submit-button");

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      status.className = "status";
      status.textContent = "Running scrape...";
      button.disabled = true;
      output.textContent = "{}";

      try {
        const response = await fetch(`/api/profile?url=${encodeURIComponent(input.value)}`);
        const text = await response.text();
        let payload;
        try {
          payload = JSON.parse(text);
          output.textContent = JSON.stringify(payload, null, 2);
        } catch {
          output.textContent = text || "{}";
        }
        if (!response.ok) {
          throw new Error(payload?.detail || `Request failed with ${response.status}`);
        }
        status.textContent = "Done";
      } catch (error) {
        status.className = "status error";
        status.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
  </script>
</body>
</html>
"""

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
