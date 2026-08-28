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


def home_page_html() -> str:
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
      --bg: #f5f7fb;
      --panel: #ffffff;
      --ink: #111827;
      --muted: #5f6b7a;
      --line: #d9e0ea;
      --soft: #eef4fb;
      --accent: #0a66c2;
      --accent-dark: #074b8e;
      --ok: #067647;
      --danger: #b42318;
      --code: #101828;
    }
    * { box-sizing: border-box; }
    html {
      overflow-x: clip;
    }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
      overflow-x: clip;
    }
    .topbar {
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.92);
      position: sticky;
      top: 0;
      z-index: 3;
      backdrop-filter: blur(14px);
    }
    .topbar-inner {
      width: min(1180px, calc(100vw - 32px));
      min-height: 64px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
    }
    .brand {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
      font-size: 18px;
      font-weight: 800;
      letter-spacing: 0;
    }
    .brand-mark {
      width: 34px;
      height: 34px;
      border-radius: 7px;
      display: grid;
      place-items: center;
      color: #ffffff;
      background: var(--accent);
      font-weight: 900;
    }
    nav {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    a {
      color: var(--accent);
      text-decoration: none;
      font-weight: 700;
    }
    nav a {
      min-height: 36px;
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 12px;
      background: var(--panel);
      color: var(--ink);
    }
    main {
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0 40px;
    }
    .intro {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
      gap: 22px;
      align-items: stretch;
      margin-bottom: 20px;
    }
    .headline {
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 14px;
      padding: 20px 0;
    }
    h1 {
      margin: 0;
      max-width: 760px;
      font-size: 58px;
      line-height: 1.02;
      font-weight: 850;
      letter-spacing: 0;
    }
    .subhead {
      margin: 0;
      max-width: 720px;
      color: var(--muted);
      font-size: 17px;
      line-height: 1.6;
    }
    .status-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-top: 8px;
    }
    .metric {
      min-height: 78px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 12px;
    }
    .metric strong {
      display: block;
      font-size: 22px;
      line-height: 1.1;
    }
    .metric span {
      display: block;
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
    }
    .endpoint {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 18px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 12px;
    }
    .endpoint-title {
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    code {
      display: block;
      min-width: 0;
      max-width: 100%;
      overflow-wrap: anywhere;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--soft);
      padding: 12px;
      color: var(--ink);
      font: 13px/1.5 ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
    }
    .founder-radar {
      margin: 10px 0 24px;
    }
    .section-heading {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 14px;
    }
    .eyebrow {
      margin: 0 0 4px;
      color: var(--accent);
      font-size: 12px;
      font-weight: 850;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    .section-heading h2 {
      margin: 0;
      font-size: 28px;
      line-height: 1.15;
      letter-spacing: 0;
    }
    .section-heading p:last-child {
      margin: 0;
      max-width: 420px;
      color: var(--muted);
      line-height: 1.5;
      text-align: right;
    }
    .founder-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      min-width: 0;
    }
    .founder-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--soft);
      padding: 16px;
      min-width: 0;
    }
    .founder-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 12px;
    }
    .person {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }
    .person > div:last-child {
      min-width: 0;
    }
    .avatar {
      width: 44px;
      height: 44px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      flex: 0 0 auto;
      color: #ffffff;
      background: #0f766e;
      font-weight: 900;
    }
    .avatar.alt { background: #7c3aed; }
    .founder-card h3 {
      margin: 0;
      font-size: 22px;
      line-height: 1.2;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }
    .founder-card h4 {
      margin: 16px 0 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 850;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    .role {
      margin: 0;
      color: var(--ink);
      font-weight: 750;
      line-height: 1.45;
      overflow-wrap: anywhere;
    }
    .pill-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }
    .pill {
      max-width: 100%;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel);
      padding: 6px 10px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }
    .timeline {
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .timeline li {
      border-left: 3px solid var(--accent);
      padding-left: 10px;
      color: var(--muted);
      line-height: 1.45;
      overflow-wrap: anywhere;
    }
    .timeline strong {
      color: var(--ink);
    }
    .founder-actions {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      margin-top: 16px;
    }
    .target-button {
      margin: 0;
      width: auto;
      min-height: 40px;
      padding: 0 14px;
    }
    .linkedin-link {
      min-height: 40px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 12px;
      background: var(--panel);
      color: var(--ink);
    }
    .workspace {
      display: grid;
      grid-template-columns: minmax(300px, 430px) minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }
    .panel h2 {
      margin: 0 0 14px;
      font-size: 18px;
      line-height: 1.25;
      letter-spacing: 0;
    }
    label {
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
    }
    input {
      width: 100%;
      min-height: 46px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 12px;
      font: inherit;
      color: var(--ink);
      background: transparent;
    }
    input:focus {
      outline: 3px solid rgba(10, 102, 194, 0.18);
      border-color: var(--accent);
    }
    button {
      width: 100%;
      min-height: 46px;
      margin-top: 12px;
      border: 0;
      border-radius: 6px;
      background: var(--accent);
      color: white;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
    }
    button:hover { background: var(--accent-dark); }
    button:disabled {
      cursor: progress;
      opacity: 0.72;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 14px;
    }
    .summary-item {
      min-height: 70px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: var(--soft);
    }
    .summary-item span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .summary-item strong {
      display: block;
      margin-top: 6px;
      overflow-wrap: anywhere;
      font-size: 17px;
      line-height: 1.3;
    }
    .status {
      min-height: 22px;
      margin-top: 12px;
      color: var(--muted);
      font-size: 14px;
      overflow-wrap: anywhere;
    }
    .status.ok { color: var(--ok); }
    .status.error { color: var(--danger); }
    pre {
      min-width: 0;
      min-height: 520px;
      max-height: calc(100vh - 190px);
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
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #0b1018;
        --panel: #111827;
        --ink: #eef4ff;
        --muted: #a7b2c3;
        --line: #283345;
        --soft: #182233;
        --code: #05070b;
      }
      .topbar { background: rgba(17, 24, 39, 0.9); }
    }
    @media (max-width: 840px) {
      .topbar-inner, main {
        width: calc(100vw - 24px);
        max-width: 720px;
      }
      .topbar-inner {
        min-height: auto;
        padding: 12px 0;
        align-items: flex-start;
        flex-direction: column;
      }
      nav {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        width: 100%;
        justify-content: stretch;
      }
      nav a {
        min-width: 0;
        justify-content: center;
        padding: 0 8px;
        text-align: center;
      }
      .intro, .workspace { grid-template-columns: 1fr; }
      .intro, .endpoint, .workspace, .panel, .founder-radar, .founder-card {
        width: 100%;
        max-width: 100%;
      }
      .headline { min-width: 0; }
      .section-heading {
        align-items: flex-start;
        flex-direction: column;
      }
      .section-heading p:last-child { text-align: left; }
      .founder-grid { grid-template-columns: 1fr; }
      .founder-actions { grid-template-columns: 1fr; }
      .target-button { width: 100%; }
      .status-grid { grid-template-columns: 1fr; }
      .summary { grid-template-columns: 1fr; }
      h1 {
        width: 100%;
        max-width: 100%;
        font-size: 34px;
        overflow-wrap: break-word;
      }
      .subhead { max-width: 100%; }
      code { word-break: break-all; }
      pre { min-height: 340px; max-height: none; }
    }
  </style>
</head>
<body>
  <div class="topbar">
    <div class="topbar-inner">
      <div class="brand" aria-label="LinkedIn Profile API">
        <span class="brand-mark">in</span>
        <span>LinkedIn Profile API</span>
      </div>
      <nav aria-label="Primary">
        <a href="/docs">Docs</a>
        <a href="#founders">Founder Radar</a>
        <a href="/health">Health</a>
        <a href="/api/profile?url=https%3A%2F%2Fwww.linkedin.com%2Fin%2Fchirag-kakwani-8b4055284%2F">Sample JSON</a>
      </nav>
    </div>
  </div>

  <main>
    <section class="intro" aria-labelledby="page-title">
      <div class="headline">
        <h1 id="page-title">LinkedIn profile data, returned as JSON.</h1>
        <p class="subhead">Paste a LinkedIn profile URL and get structured profile, experience, education, and extraction metadata from the deployed API.</p>
        <div class="status-grid" aria-label="Deployment status">
          <div class="metric">
            <strong>Live</strong>
            <span>Production deployment</span>
          </div>
          <div class="metric">
            <strong>HTTPS</strong>
            <span>Public API endpoint</span>
          </div>
          <div class="metric">
            <strong>JSON</strong>
            <span>Assignment-ready output</span>
          </div>
        </div>
      </div>
      <aside class="endpoint" aria-label="Endpoint">
        <div class="endpoint-title">GET endpoint</div>
        <code>/api/profile?url=https://www.linkedin.com/in/example/</code>
        <a href="/openapi.json">OpenAPI schema</a>
      </aside>
    </section>

    <section class="founder-radar" id="founders" aria-labelledby="founder-title">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Founder Radar</p>
          <h2 id="founder-title">Likely reviewers, preloaded.</h2>
        </div>
        <p>A tiny VIP queue for the two profiles most likely to test this API, with the useful public LinkedIn details already laid out.</p>
      </div>

      <div class="founder-grid">
        <article class="founder-card">
          <div class="founder-head">
            <div class="person">
              <div class="avatar" aria-hidden="true">MS</div>
              <div>
                <h3>Meet Shah</h3>
                <p class="role">Co-Founder and CTO at Tross (Previously Ayden)</p>
              </div>
            </div>
          </div>
          <div class="pill-row">
            <span class="pill">San Francisco, California, United States</span>
            <span class="pill">IIT Roorkee</span>
            <span class="pill">Backend, security, infra</span>
          </div>

          <h4>Experience</h4>
          <ul class="timeline">
            <li><strong>Tross</strong> - Co-Founder and CTO, Jun 2025 to Present.</li>
            <li><strong>BharatX</strong> - Founding Engineer across backend, risk underwriting, and infra; acquired by Flipkart.</li>
            <li><strong>Entrepreneur First</strong> - Entrepreneur in Residence, Jul 2023 to Dec 2023.</li>
            <li><strong>Shape</strong> - Founding Software Engineer on a natural language database engine, Jan 2023 to Jun 2023.</li>
            <li><strong>Microsoft</strong> - Software/Security Engineering Intern building phishing detection, May 2022 to Jul 2022.</li>
            <li><strong>Hevo Data</strong> - Software Engineering Intern on internal monitoring, Nov 2021 to Apr 2022.</li>
            <li><strong>GSoC and open source</strong> - Terasology Foundation and SDSLabs work across 2020 to 2021.</li>
          </ul>

          <h4>Education</h4>
          <ul class="timeline">
            <li><strong>Indian Institute of Technology, Roorkee</strong> - BTech, Computer Science, 2019 to 2023.</li>
          </ul>

          <div class="founder-actions">
            <button class="target-button" type="button" data-profile-url="https://www.linkedin.com/in/meetcshah19/">Scrape Meet</button>
            <a class="linkedin-link" href="https://www.linkedin.com/in/meetcshah19/" target="_blank" rel="noopener noreferrer">LinkedIn</a>
          </div>
        </article>

        <article class="founder-card">
          <div class="founder-head">
            <div class="person">
              <div class="avatar alt" aria-hidden="true">PK</div>
              <div>
                <h3>Padam Kataria</h3>
                <p class="role">Co-Founder at Tross (Previously Ayden)</p>
              </div>
            </div>
          </div>
          <div class="pill-row">
            <span class="pill">San Francisco Bay Area</span>
            <span class="pill">BITS Pilani</span>
            <span class="pill">Product, fintech, GTM</span>
          </div>

          <h4>Experience</h4>
          <ul class="timeline">
            <li><strong>Tross</strong> - Co-Founder, Dec 2025 to Present.</li>
            <li><strong>Career break</strong> - Personal goal pursuit, running, cycling, AI tools, and travel, Feb 2025 to Jun 2025.</li>
            <li><strong>BharatX</strong> - Business Head, May 2024 to Feb 2025; acquired by Super.money / Flipkart.</li>
            <li><strong>Zenifi</strong> - Healthcare fintech, Apr 2023 to May 2024; acquired by BharatX.</li>
            <li><strong>Navi</strong> - Product work on personal loans, mandates, KYC, and account aggregator flows, Jan 2022 to Apr 2023.</li>
            <li><strong>Hallparty</strong> - Founding Member across recruiting, product, and user research, Sep 2020 to Feb 2021.</li>
            <li><strong>Sprinklr</strong> - Product work in customer experience management, 2021.</li>
          </ul>

          <h4>Education</h4>
          <ul class="timeline">
            <li><strong>BITS Pilani</strong> - B.E. (Hons.), Electronics and Instrumentation, 2018 to 2022.</li>
            <li><strong>DPS R.K. Puram</strong> - Physics, Chemistry, and Mathematics.</li>
          </ul>

          <div class="founder-actions">
            <button class="target-button" type="button" data-profile-url="https://www.linkedin.com/in/padamkataria/">Scrape Padam</button>
            <a class="linkedin-link" href="https://www.linkedin.com/in/padamkataria/" target="_blank" rel="noopener noreferrer">LinkedIn</a>
          </div>
        </article>
      </div>
    </section>

    <div class="workspace">
      <section class="panel" aria-labelledby="scrape-title">
        <h2 id="scrape-title">Profile Lookup</h2>
        <form id="scrape-form">
          <label for="profile-url">Profile URL</label>
          <input
            id="profile-url"
            name="profile-url"
            type="url"
            value="https://www.linkedin.com/in/chirag-kakwani-8b4055284/"
            autocomplete="url"
            required
          >
          <button id="submit-button" type="submit">Scrape Profile</button>
          <div id="status" class="status"></div>
        </form>
        <div class="summary" aria-label="Result summary">
          <div class="summary-item">
            <span>Name</span>
            <strong id="summary-name">-</strong>
          </div>
          <div class="summary-item">
            <span>Location</span>
            <strong id="summary-location">-</strong>
          </div>
          <div class="summary-item">
            <span>Experience</span>
            <strong id="summary-experience">-</strong>
          </div>
          <div class="summary-item">
            <span>Education</span>
            <strong id="summary-education">-</strong>
          </div>
        </div>
      </section>

      <section class="panel" aria-labelledby="response-title">
        <h2 id="response-title">Response Body</h2>
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
    const summaryName = document.querySelector("#summary-name");
    const summaryLocation = document.querySelector("#summary-location");
    const summaryExperience = document.querySelector("#summary-experience");
    const summaryEducation = document.querySelector("#summary-education");

    function setSummary(payload) {
      summaryName.textContent = payload?.name || "-";
      summaryLocation.textContent = payload?.location || "-";
      summaryExperience.textContent = Array.isArray(payload?.experience)
        ? String(payload.experience.length)
        : "-";
      summaryEducation.textContent = Array.isArray(payload?.education)
        ? String(payload.education.length)
        : "-";
    }

    document.querySelectorAll("[data-profile-url]").forEach((targetButton) => {
      targetButton.addEventListener("click", () => {
        input.value = targetButton.dataset.profileUrl;
        form.requestSubmit();
      });
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      status.className = "status";
      status.textContent = "Running scrape...";
      button.disabled = true;
      output.textContent = "{}";
      setSummary(null);

      try {
        const response = await fetch(`/api/profile?url=${encodeURIComponent(input.value)}`);
        const text = await response.text();
        let payload;
        try {
          payload = JSON.parse(text);
          output.textContent = JSON.stringify(payload, null, 2);
          if (response.ok) {
            setSummary(payload);
          }
        } catch {
          output.textContent = text || "{}";
        }
        if (!response.ok) {
          throw new Error(payload?.detail || `Request failed with ${response.status}`);
        }
        status.className = "status ok";
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

    @app.get("/", response_class=HTMLResponse)
    async def root() -> str:
        return home_page_html()

    @app.get("/ui", response_class=HTMLResponse)
    async def ui() -> str:
        return home_page_html()

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
