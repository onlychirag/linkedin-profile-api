# LinkedIn Profile API

FastAPI service for the engineer hiring challenge. It accepts a LinkedIn profile URL and returns structured JSON for profile metadata, experience, education, skills, certifications, languages, and images when LinkedIn exposes them to the configured backend session.

This implementation avoids the brittle "paste LinkedIn cookies into requests" method. It uses three strategies:

1. Public metadata parsing from Open Graph and JSON-LD.
2. DrissionPage or Playwright browser navigation with a backend-owned LinkedIn session.
3. Detail-page extraction for `/details/experience/`, `/details/education/`, `/details/skills/`, `/details/certifications/`, and `/details/languages/`.

The service does not bypass login, MFA, checkpoints, paywalls, or private profile visibility. It only extracts what the configured LinkedIn account can view.

## API

### Health

```http
GET /health
```

### Scrape a profile

```http
POST /api/v1/profiles
Content-Type: application/json
X-API-Key: optional-if-configured

{
  "url": "https://www.linkedin.com/in/example/"
}
```

Equivalent GET endpoint:

```http
GET /api/v1/profiles?url=https://www.linkedin.com/in/example/
```

Compatibility endpoint:

```http
GET /api/profile?url=https://www.linkedin.com/in/example/
```

Example response shape:

```json
{
  "profile_url": "https://www.linkedin.com/in/example/",
  "public_identifier": "example",
  "name": "Jane Doe",
  "headline": "Staff Engineer",
  "location": "Bengaluru, India",
  "about": "Backend engineer focused on APIs and data systems.",
  "profile_images": [],
  "experience": [],
  "education": [],
  "skills": [],
  "certifications": [],
  "languages": [],
  "raw_sections": {},
  "extraction": {
    "requested_url": "https://www.linkedin.com/in/example/",
    "resolved_url": "https://www.linkedin.com/in/example/",
    "public_identifier": "example",
    "authenticated": true,
    "strategies": ["public-metadata", "playwright-profile-page"],
    "warnings": [],
    "scraped_at": "2026-08-28T00:00:00Z"
  }
}
```

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open API docs at `http://localhost:8000/docs`.

## Authentication options

### Option A: backend credentials

Set these as environment variables in `.env` locally or as secrets on your host:

```bash
LINKEDIN_EMAIL=you@example.com
LINKEDIN_PASSWORD=your-password
```

The first request opens a headless Playwright browser, logs in, and saves a storage state at `.auth/linkedin-state.json`. If LinkedIn requires MFA or checkpoint verification, use Option B.

### Option B: manual browser session

```bash
python scripts/create_linkedin_session.py --email you@example.com
```

Finish login in the browser window. The script automatically waits until LinkedIn shows a signed-in feed, then writes a persistent browser profile to `.auth/linkedin-browser-profile`, a success marker inside that profile directory, and a portable storage state to `.auth/linkedin-state.json`. All are ignored by Git.

The persistent browser profile is the preferred local method because LinkedIn sometimes rejects exported cookies or storage-state files. The API uses it automatically after the success marker exists.

If Chromium or LinkedIn gets stuck with an old profile, create a fresh one without deleting the old files:

```bash
python scripts/create_linkedin_session.py --fresh --email you@example.com
```

For hosted environments that cannot mount files, base64 the storage-state JSON and set it as a secret:

```bash
powershell -Command "[Convert]::ToBase64String([IO.File]::ReadAllBytes('.auth/linkedin-state.json'))"
```

Save the output to:

```bash
LINKEDIN_STORAGE_STATE_B64=...
```

## Recommended hosting

Use Render for this challenge deployment. The scraper needs a Docker runtime,
Chromium, and longer request handling than a typical serverless function. Vercel
is a good frontend host, but the browser-backed scraper is a poor fit for Vercel
Functions.

The repo includes a `Dockerfile` and `render.yaml` for Render.

Free Render steps:

1. Push this repository to GitHub.
2. Create a new Render Web Service from the repository.
3. Choose the Free plan.
4. Set `LINKEDIN_STORAGE_STATE_B64` from your local `.auth/linkedin-state.json`.
5. Leave `API_KEY` empty for assignment testing unless your evaluator will send it.
6. Deploy. Render provides the public HTTPS URL.

Free Render services spin down when idle, do not provide persistent disks, and
are too small for reliable Chromium scraping. The included free config disables
browser launch and uses the stored LinkedIn session for authenticated HTTP HTML
fetches instead. If the LinkedIn session expires or LinkedIn asks for a
checkpoint, refresh the local session and update `LINKEDIN_STORAGE_STATE_B64` in
Render.

Vercel trial steps:

1. Import this GitHub repo as a new Vercel project.
2. Leave the framework preset as Other.
3. Set `LINKEDIN_STORAGE_STATE_B64` as a Production environment variable.
4. Deploy.

The repo includes `api/index.py`, `pyproject.toml`, and `vercel.json` so Vercel
uses its Python runtime with lightweight dependencies and browser scraping
disabled. The Vercel deployment is for the authenticated HTTP scraper only; it
does not install or launch Playwright/Chromium.

### Hybrid Vercel + Oracle Cloud

For full skills, certifications, and profile photos, run the scraper on an
Oracle Cloud VM and keep Vercel as the public website. In this mode, Vercel
serves the UI and forwards `/api/profile` plus `/api/image` to the Oracle API.

Oracle `.env`:

```bash
API_KEY=choose-a-long-secret
ENABLE_BROWSER_SCRAPER=true
ENABLE_AUTH_HTTP_SCRAPER=true
ENABLE_DRISSION_SCRAPER=false
BROWSER_BACKEND=playwright
PLAYWRIGHT_HEADLESS=true
REQUEST_TIMEOUT_MS=180000
LINKEDIN_STORAGE_STATE_B64=...
ALLOWED_ORIGINS=https://your-vercel-app.vercel.app
```

Oracle Docker run:

```bash
docker build -t linkedin-profile-api .
docker run -d --name linkedin-profile-api --restart unless-stopped \
  -p 8000:8000 --env-file .env linkedin-profile-api
```

Vercel environment variables:

```bash
UPSTREAM_API_BASE_URL=https://your-oracle-api.example.com
UPSTREAM_API_KEY=choose-a-long-secret
ENABLE_BROWSER_SCRAPER=false
ENABLE_DRISSION_SCRAPER=false
REQUEST_TIMEOUT_MS=180000
```

Use HTTPS for the Oracle API through Cloudflare Tunnel, Caddy, Nginx, or a
load balancer. A raw `http://oracle-ip:8000` upstream can work server-to-server,
but it exposes the upstream key over plain HTTP.

Any Docker host works too:

```bash
docker build -t linkedin-profile-api .
docker run -p 8000:8000 --env-file .env linkedin-profile-api
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `API_KEY` | empty | Optional shared key required through `X-API-Key` or `api_key`. |
| `ENABLE_BROWSER_SCRAPER` | `true` | Enables browser-backed extraction after the public metadata pass. |
| `ENABLE_AUTH_HTTP_SCRAPER` | `true` | Uses Playwright storage-state cookies for authenticated HTTP HTML extraction before launching a browser. |
| `BROWSER_BACKEND` | `auto` | `auto`, `drission`, or `playwright`. `auto` tries DrissionPage first and falls back to Playwright. |
| `ENABLE_DRISSION_SCRAPER` | `true` | Enables the optional DrissionPage backend in `auto` mode. |
| `PLAYWRIGHT_HEADLESS` | `true` | Runs Chromium headlessly. Set `false` only for local debugging. |
| `DRISSION_HEADLESS` | `true` | Runs the DrissionPage Chromium browser headlessly. |
| `DRISSION_BROWSER_PATH` | empty | Optional Chrome or Edge executable path if DrissionPage cannot auto-detect a browser. |
| `SCRAPER_USER_AGENT` | built-in Chrome-like UA | User-Agent used for direct public HTTP metadata requests. |
| `BROWSER_USER_AGENT` | empty | Optional browser User-Agent override. Leave empty so Chromium reports its real version. |
| `REQUEST_TIMEOUT_MS` | `45000` | Navigation and request timeout. |
| `LINKEDIN_EMAIL` | empty | Backend LinkedIn email. `LINKEDIN_USERNAME` is accepted as an alias. |
| `LINKEDIN_PASSWORD` | empty | Backend LinkedIn password. |
| `PROXY_URL` | empty | Optional proxy URL for the DrissionPage backend. |
| `UPSTREAM_API_BASE_URL` | empty | Optional upstream API URL. When set, this deployment proxies profile and image requests to that server instead of scraping locally. |
| `UPSTREAM_API_KEY` | empty | Optional API key sent to the upstream scraper through `X-API-Key`. |
| `LINKEDIN_USER_DATA_DIR` | `.auth/linkedin-browser-profile` | Persistent Playwright browser profile directory. |
| `LINKEDIN_STORAGE_STATE_PATH` | `.auth/linkedin-state.json` | Local Playwright session file. |
| `LINKEDIN_STORAGE_STATE_B64` | empty | Hosted session state as base64 JSON. |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins. |

## Development

```bash
pytest
```

The tests use sample HTML and dependency injection. They do not hit LinkedIn.

## Known limitations

- LinkedIn changes markup often, so parsing is intentionally heuristic and isolated in `app/scraper/parsers.py`.
- Full experience, education, skills, certifications, and languages generally require an authenticated account that can view the profile.
- LinkedIn may trigger MFA, checkpoint, or temporary restrictions. This project does not include CAPTCHA solving, proxy rotation, stealth plugins, or access-control bypasses.
- The official LinkedIn APIs do not provide arbitrary public profile scraping, so this challenge-style implementation uses browser-visible data instead.

## Methods considered

Chinese-language scraping repos commonly combine a public metadata pass with session-backed browser automation. The useful idea from that research is the backend split: use JSON-LD/Open Graph when public data is enough, then fall back to a real Chromium profile for pages that require login. This repo implements that pattern with a selectable `BROWSER_BACKEND` instead of hardcoding copied cookies.
