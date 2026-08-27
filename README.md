# LinkedIn Profile API

A reverse-engineered LinkedIn API that accepts a LinkedIn profile URL and returns structured JSON data.

## Features

- **Structured JSON output** — name, headline, location, about, experience, education, skills, certifications, languages, and profile images
- **Dual scraping strategy** — Voyager API (fast) with Playwright browser fallback (resilient)
- **Auto-generated API docs** — Swagger UI at `/docs`, ReDoc at `/redoc`
- **Deployed over HTTPS** — Free hosting on Render.com

## Live Demo

```
GET https://your-app.onrender.com/api/v1/profile?url=https://www.linkedin.com/in/williamhgates
```

## Quick Start

### Prerequisites
- Python 3.11+
- A LinkedIn account (to get session cookies)

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/linkedin-profile-api.git
cd linkedin-profile-api
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Credentials

```bash
cp .env.example .env
# Edit .env and paste your li_at cookie
```

**How to get your LinkedIn cookies:**
1. Open Chrome → go to `linkedin.com` → log in
2. Press `F12` → **Application** tab → **Cookies** → `https://www.linkedin.com`
3. Copy the value of `li_at` → paste into `.env` as `LI_AT_COOKIE`
4. Copy `JSESSIONID` (remove surrounding quotes) → paste as `JSESSIONID`

### 3. Run Locally

```bash
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs for interactive API docs.

### 4. Test

```bash
pip install pytest
pytest tests/ -v
```

## API Documentation

### `GET /api/v1/profile`

Scrapes a LinkedIn profile and returns structured data.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | Yes | LinkedIn profile URL |

**Example Request:**
```bash
curl "http://localhost:8000/api/v1/profile?url=https://www.linkedin.com/in/williamhgates"
```

**Example Response (200):**
```json
{
  "success": true,
  "profile_url": "https://www.linkedin.com/in/williamhgates",
  "first_name": "Bill",
  "last_name": "Gates",
  "full_name": "Bill Gates",
  "headline": "Co-chair, Bill & Melinda Gates Foundation",
  "location": "Seattle, Washington, United States",
  "about": "Co-chair of the Bill & Melinda Gates Foundation...",
  "profile_image_url": "https://media.licdn.com/...",
  "background_image_url": null,
  "connections_count": "500+",
  "experience": [
    {
      "title": "Co-chair",
      "company": "Bill & Melinda Gates Foundation",
      "company_logo_url": null,
      "location": "Seattle, WA",
      "start_date": "Jan 2000",
      "end_date": "Present",
      "duration": null,
      "description": null
    }
  ],
  "education": [
    {
      "school": "Harvard University",
      "degree": null,
      "field_of_study": null,
      "start_year": "1973",
      "end_year": "1975"
    }
  ],
  "skills": ["Public Speaking", "Strategic Planning"],
  "certifications": [],
  "languages": [],
  "source": "voyager"
}
```

**Error Response (400):**
```json
{
  "success": false,
  "error": "Invalid LinkedIn profile URL.",
  "detail": "Expected format: https://www.linkedin.com/in/username"
}
```

### `GET /`

Health check endpoint.

```json
{"status": "ok", "service": "linkedin-profile-api", "version": "1.0.0", "docs": "/docs"}
```

## Architecture

```
Client Request
    │
    ▼
FastAPI Router (/api/v1/profile)
    │
    ▼
URL Validation
    │
    ▼
Profile Orchestrator (Waterfall)
    ├──► [1] Voyager API Client (fast, structured JSON)
    │         Uses li_at cookie + HTTP requests to LinkedIn's internal API
    │         ├─ Success → Return ProfileResponse
    │         └─ Failure → Fall through
    │
    └──► [2] Playwright Browser (slower, resilient)
              Launches headless Chromium, renders page, extracts from DOM
              ├─ Success → Return ProfileResponse
              └─ Failure → Return 500 error
```

### Why Two Strategies?

| Strategy | Speed | Data Quality | Resilience |
|----------|-------|-------------|------------|
| **Voyager API** | ~3s | High (structured JSON) | Medium (endpoints change) |
| **Playwright** | ~15s | Medium (DOM-dependent) | High (renders like a real browser) |

The waterfall ensures the API stays functional even when LinkedIn changes their internal API.

## Deployment (Render.com)

1. Push your code to a **public GitHub repo**
2. Go to [render.com](https://render.com) → **New** → **Web Service**
3. Connect your GitHub repository
4. Render auto-detects the `Dockerfile`
5. Add environment variables in the Render dashboard:
   - `LI_AT_COOKIE` = your li_at cookie value
   - `JSESSIONID` = your JSESSIONID value
6. Click **Deploy** → you get a free `https://your-app.onrender.com` URL

## Project Structure

```
linkedin-profile-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + middleware
│   ├── config.py            # Env var config (pydantic-settings)
│   ├── schemas.py           # Pydantic response models
│   ├── routes/
│   │   └── profile.py       # GET /api/v1/profile endpoint
│   ├── services/
│   │   ├── orchestrator.py  # Waterfall strategy router
│   │   ├── voyager.py       # LinkedIn Voyager API client
│   │   └── browser.py       # Playwright browser scraper
│   └── utils/
│       └── parsing.py       # URL parsing, text cleaning
├── tests/
│   ├── test_schemas.py
│   └── test_profile.py
├── .env.example
├── .gitignore
├── Dockerfile
├── requirements.txt
├── render.yaml
└── README.md
```

## Known Limitations

1. **Cookie Expiry** — The `li_at` cookie can expire or be revoked. You'll need to refresh it manually by re-extracting from your browser.
2. **Rate Limiting** — LinkedIn may throttle or block requests if too many are sent. Built-in random delays (2-5s) help, but high-volume usage is risky.
3. **DOM Fragility** — The browser fallback uses CSS selectors that may break when LinkedIn redesigns their UI.
4. **Render Cold Start** — On the free tier, the service sleeps after 15 minutes of inactivity. The first request after sleep takes ~30-60 seconds.
5. **Incomplete Profiles** — Some profiles have restricted visibility; fields may return `null`.
6. **Terms of Service** — Scraping LinkedIn violates their ToS. This project is built as a hiring challenge demonstration.

## Tech Stack

- **FastAPI** — Modern async Python web framework
- **Pydantic v2** — Data validation and serialization
- **httpx** — Async HTTP client for Voyager API calls
- **Playwright** — Browser automation for fallback scraping
- **Uvicorn** — ASGI server
- **Docker** — Containerization
- **Render.com** — Deployment platform

## License

MIT
