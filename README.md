# LinkedIn Profile API

A cookie-free REST API that accepts a LinkedIn profile URL and returns structured profile data.

## Approach

LinkedIn's internal APIs (Voyager) require authenticated session cookies, which are fragile, rate-limited, and violate ToS when scraped. Instead, this API uses **Proxycurl**, a legitimate data enrichment service that provides structured LinkedIn profile data via a simple API key — no browser automation, no cookies, no session management.

### Why this approach?
- **No cookies/auth sessions** — just an API key
- **No browser automation** — no Puppeteer/Playwright overhead
- **Structured data** — no HTML parsing fragility
- **Legal & ethical** — uses publicly available professional data via a licensed provider
- **Production-ready** — handles retries, caching, and rate limits automatically

## Setup

1. Clone the repo
2. Copy `.env.example` to `.env` and add your Proxycurl API key:
   ```bash
   cp .env.example .env
   ```
   Get a free API key at [proxycurl.com](https://proxycurl.com) (10 free credits to start).
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run locally:
   ```bash
   uvicorn main:app --reload
   ```

## API Documentation

Once running, visit `/docs` for interactive Swagger UI.

### `GET /api/profile`

**Query Params:**
- `url` (required) — Full LinkedIn profile URL, e.g. `https://www.linkedin.com/in/williamhgates/`

**Response:**
```json
{
  "name": "Bill Gates",
  "headline": "Co-chair, Bill & Melinda Gates Foundation",
  "location": "Seattle, Washington, United States",
  "about": "...",
  "experience": [
    {
      "title": "Co-chair",
      "company": "Bill & Melinda Gates Foundation",
      "location": null,
      "start_date": "2000",
      "end_date": null,
      "description": null
    }
  ],
  "education": [...],
  "skills": ["Philanthropy", "Global Health"],
  "certifications": [...],
  "languages": ["English"],
  "profile_image": "https://..."
}
```

## Deployment

### Render (Recommended — Free Tier)
1. Push to GitHub
2. Create a new Web Service on [Render](https://render.com)
3. Connect your repo
4. Set environment variable `PROXYCURL_API_KEY`
5. Build command: leave blank (uses Dockerfile)
6. Start command: leave blank (uses Dockerfile)

### Railway / Fly.io / Heroku
All support Docker deployments. Set the `PROXYCURL_API_KEY` env var and deploy.

## Known Limitations

- Requires a Proxycurl API key (free tier: 10 credits, paid plans available)
- Profiles with very restrictive privacy settings may return partial data
- Rate limits depend on your Proxycurl plan
- Does not return email or contact info (not available via this endpoint)
