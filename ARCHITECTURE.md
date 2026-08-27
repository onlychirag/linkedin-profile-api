# LinkedIn Profile API — Architecture & Implementation Blueprint

## Challenge Summary

Build a publicly-hosted HTTPS API that accepts a LinkedIn profile URL and returns structured JSON with: name, headline, location, about, experience, education, skills, certifications, languages, and profile images.

---

## Architecture Decision: Dual-Strategy Scraper

We use **two strategies in a waterfall pattern**:

1. **Primary — Voyager API** (fast, structured, low resource): Direct HTTP calls to LinkedIn's internal API using an authenticated `li_at` session cookie. Returns clean JSON.
2. **Fallback — Playwright Browser** (slower, resilient): If Voyager fails (cookie expired, endpoint changed), fall back to headless browser scraping with stealth plugins.

```
User Request → FastAPI → Strategy Router
                            ├─► Voyager API Client (primary)
                            │     ├─ Success → Parse → Return JSON
                            │     └─ Failure ──┐
                            └─► Playwright Scraper (fallback)
                                  └─ Parse DOM → Return JSON
```

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Web Framework | **FastAPI** (Python 3.11+) | Async, auto-docs, Pydantic integration |
| Validation | **Pydantic v2** | Type-safe response schemas |
| Primary Scraper | **httpx** (async HTTP) | Async requests to Voyager endpoints |
| Fallback Scraper | **Playwright** | Stealth browser automation |
| Server | **Uvicorn** | ASGI production server |
| Deployment | **Render.com** (free tier) | Free HTTPS, auto-deploy from GitHub |
| Secrets | **pydantic-settings** | Load from env vars, never hardcode |

---

## Project Structure

```
linkedin-profile-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, middleware, exception handlers
│   ├── config.py            # Settings from env vars
│   ├── schemas.py           # ALL Pydantic response models
│   ├── routes/
│   │   ├── __init__.py
│   │   └── profile.py       # GET /api/v1/profile endpoint
│   ├── services/
│   │   ├── __init__.py
│   │   ├── orchestrator.py  # Waterfall strategy router
│   │   ├── voyager.py       # Voyager API client
│   │   └── browser.py       # Playwright fallback scraper
│   └── utils/
│       ├── __init__.py
│       └── parsing.py       # Shared parsing/cleaning helpers
├── tests/
│   ├── __init__.py
│   ├── test_schemas.py
│   └── test_profile.py
├── .env.example             # Template for secrets
├── .gitignore
├── Dockerfile
├── requirements.txt
├── render.yaml              # Render deployment config
└── README.md
```

---

## File-by-File Implementation Details

### 1. `app/config.py` — Settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LinkedIn session cookie (from browser DevTools > Application > Cookies > li_at)
    LI_AT_COOKIE: str
    # Optional: JSESSIONID cookie for CSRF token
    JSESSIONID: str = ""
    # Rate limiting
    REQUEST_DELAY_MIN: float = 2.0
    REQUEST_DELAY_MAX: float = 5.0
    # App
    APP_ENV: str = "production"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

### 2. `app/schemas.py` — Response Models

Every field is `Optional` because LinkedIn profiles have variable completeness.

```python
from pydantic import BaseModel, Field
from typing import Optional

class Experience(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    company_logo_url: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None

class Education(BaseModel):
    school: Optional[str] = None
    school_logo_url: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[str] = None
    end_year: Optional[str] = None
    description: Optional[str] = None

class Certification(BaseModel):
    name: Optional[str] = None
    issuing_organization: Optional[str] = None
    issue_date: Optional[str] = None
    credential_url: Optional[str] = None

class Language(BaseModel):
    name: Optional[str] = None
    proficiency: Optional[str] = None

class ProfileResponse(BaseModel):
    success: bool = True
    profile_url: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    about: Optional[str] = None
    profile_image_url: Optional[str] = None
    background_image_url: Optional[str] = None
    connections_count: Optional[str] = None
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    source: str = "voyager"

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
```

### 3. `app/services/voyager.py` — Primary Strategy (Voyager API)

This calls LinkedIn's internal Voyager API directly via HTTP. The key insight: LinkedIn's frontend uses these same endpoints. We replicate those calls with proper headers and cookies.

**How Voyager API works:**
- Endpoint: `GET https://www.linkedin.com/voyager/api/identity/profiles/{public_id}/profileView`
- Auth: `li_at` cookie + `Csrf-Token` header (derived from JSESSIONID)
- Response: A normalized JSON blob with an `included` array containing typed entities (`Profile`, `Position`, `Education`, `Skill`, etc.)
- Each entity has a `$type` field to identify what it is

```python
import httpx
import asyncio
import random
import calendar
import logging
from app.config import settings
from app.schemas import ProfileResponse, Experience, Education, Certification, Language

logger = logging.getLogger(__name__)

class VoyagerClient:
    BASE_URL = "https://www.linkedin.com/voyager/api"
    
    def __init__(self):
        csrf = settings.JSESSIONID.strip('"') if settings.JSESSIONID else "ajax:0"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/vnd.linkedin.normalized+json+2.1",
            "X-Restli-Protocol-Version": "2.0.0",
            "Csrf-Token": csrf,
        }
        self.cookies = {"li_at": settings.LI_AT_COOKIE}
        if settings.JSESSIONID:
            self.cookies["JSESSIONID"] = settings.JSESSIONID

    def _extract_public_id(self, url: str) -> str:
        """
        Extract public profile ID from LinkedIn URL.
        Input:  'https://www.linkedin.com/in/john-doe-123/'
        Output: 'john-doe-123'
        """
        url = url.rstrip("/")
        parts = url.split("/in/")
        if len(parts) < 2:
            raise ValueError(f"Invalid LinkedIn URL: {url}")
        return parts[1].split("/")[0].split("?")[0]

    async def get_profile(self, profile_url: str) -> ProfileResponse:
        public_id = self._extract_public_id(profile_url)
        
        # Random delay to mimic human behavior
        delay = random.uniform(settings.REQUEST_DELAY_MIN, settings.REQUEST_DELAY_MAX)
        await asyncio.sleep(delay)

        async with httpx.AsyncClient(
            headers=self.headers, cookies=self.cookies, timeout=30
        ) as client:
            resp = await client.get(
                f"{self.BASE_URL}/identity/profiles/{public_id}/profileView"
            )
            resp.raise_for_status()
            data = resp.json()

        return self._parse_profile(data, profile_url)

    def _parse_profile(self, data: dict, profile_url: str) -> ProfileResponse:
        """
        Parse the Voyager API JSON response.
        
        Structure of the response:
        {
          "data": { ... references to entities ... },
          "included": [
            {"$type": "com.linkedin.voyager.identity.profile.Profile", "firstName": "...", ...},
            {"$type": "com.linkedin.voyager.identity.profile.Position", "title": "...", ...},
            {"$type": "com.linkedin.voyager.identity.profile.Education", "schoolName": "...", ...},
            {"$type": "com.linkedin.voyager.identity.profile.Skill", "name": "...", ...},
            ...
          ]
        }
        
        We iterate through 'included' and filter by '$type' to extract each section.
        """
        included = data.get("included", [])

        # Find main profile entity
        profile = {}
        for item in included:
            if item.get("$type", "").endswith(".Profile"):
                profile = item
                break

        # Parse experiences
        experiences = []
        for item in included:
            t = item.get("$type", "")
            if "Position" in t:
                tp = item.get("timePeriod", {}) or {}
                experiences.append(Experience(
                    title=item.get("title"),
                    company=item.get("companyName"),
                    location=item.get("locationName"),
                    description=item.get("description"),
                    start_date=self._fmt_date(tp.get("startDate")),
                    end_date=self._fmt_date(tp.get("endDate")),
                ))

        # Parse education
        educations = []
        for item in included:
            t = item.get("$type", "")
            if "Education" in t and item.get("schoolName"):
                tp = item.get("timePeriod", {}) or {}
                sd = tp.get("startDate", {}) or {}
                ed = tp.get("endDate", {}) or {}
                educations.append(Education(
                    school=item.get("schoolName"),
                    degree=item.get("degreeName"),
                    field_of_study=item.get("fieldOfStudy"),
                    description=item.get("description"),
                    start_year=str(sd.get("year", "")) if sd.get("year") else None,
                    end_year=str(ed.get("year", "")) if ed.get("year") else None,
                ))

        # Parse skills
        skills = [item["name"] for item in included
                  if "Skill" in item.get("$type", "") and item.get("name")]

        # Parse certifications
        certs = []
        for item in included:
            if "Certification" in item.get("$type", ""):
                certs.append(Certification(
                    name=item.get("name"),
                    issuing_organization=item.get("authority"),
                    credential_url=item.get("url"),
                ))

        # Parse languages
        langs = []
        for item in included:
            if "Language" in item.get("$type", ""):
                langs.append(Language(
                    name=item.get("name"),
                    proficiency=item.get("proficiency"),
                ))

        # Extract profile image (find largest artifact)
        profile_pic = None
        for item in included:
            if "ProfilePicture" in str(item.get("$type", "")):
                ref = item.get("displayImageReference", {})
                vec = ref.get("vectorImage", {})
                artifacts = vec.get("artifacts", [])
                if artifacts:
                    root = vec.get("rootUrl", "")
                    largest = max(artifacts, key=lambda a: a.get("width", 0))
                    seg = largest.get("fileIdentifyingUrlPathSegment", "")
                    profile_pic = root + seg

        return ProfileResponse(
            profile_url=profile_url,
            first_name=profile.get("firstName"),
            last_name=profile.get("lastName"),
            full_name=f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip() or None,
            headline=profile.get("headline"),
            location=profile.get("locationName"),
            about=profile.get("summary"),
            profile_image_url=profile_pic,
            experience=experiences,
            education=educations,
            skills=skills,
            certifications=certs,
            languages=langs,
            source="voyager",
        )

    def _fmt_date(self, date_obj) -> str | None:
        if not date_obj or not isinstance(date_obj, dict):
            return None
        month = date_obj.get("month")
        year = date_obj.get("year")
        if month and year:
            return f"{calendar.month_abbr[int(month)]} {year}"
        return str(year) if year else None
```

### 4. `app/services/browser.py` — Fallback Strategy (Playwright)

```python
from playwright.async_api import async_playwright
from app.config import settings
from app.schemas import ProfileResponse

class BrowserScraper:
    async def get_profile(self, profile_url: str) -> ProfileResponse:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            await context.add_cookies([{
                "name": "li_at",
                "value": settings.LI_AT_COOKIE,
                "domain": ".linkedin.com",
                "path": "/",
            }])
            
            page = await context.new_page()
            await page.goto(profile_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            
            # Scroll to trigger lazy loading of all sections
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 800)")
                await page.wait_for_timeout(1000)

            # Extract all data in a single page.evaluate call
            data = await page.evaluate("""() => {
                const getText = (sel) => {
                    const el = document.querySelector(sel);
                    return el ? el.innerText.trim() : null;
                };
                const getImgSrc = (sel) => {
                    const el = document.querySelector(sel);
                    return el ? el.src : null;
                };
                return {
                    name: getText('h1'),
                    headline: getText('.text-body-medium.break-words'),
                    location: getText('.text-body-small.inline.t-black--light.break-words'),
                    about: getText('#about ~ div .inline-show-more-text'),
                    profileImage: getImgSrc('img.pv-top-card-profile-picture__image--show'),
                };
            }""")

            await browser.close()

        name_parts = (data.get("name") or "").split(" ", 1)
        return ProfileResponse(
            profile_url=profile_url,
            first_name=name_parts[0] if name_parts else None,
            last_name=name_parts[1] if len(name_parts) > 1 else None,
            full_name=data.get("name"),
            headline=data.get("headline"),
            location=data.get("location"),
            about=data.get("about"),
            profile_image_url=data.get("profileImage"),
            source="browser",
        )
```

### 5. `app/services/orchestrator.py` — Waterfall Router

```python
import logging
from app.services.voyager import VoyagerClient
from app.services.browser import BrowserScraper
from app.schemas import ProfileResponse

logger = logging.getLogger(__name__)

class ProfileOrchestrator:
    def __init__(self):
        self.voyager = VoyagerClient()
        self.browser = BrowserScraper()

    async def get_profile(self, profile_url: str) -> ProfileResponse:
        # Strategy 1: Voyager API (fast, structured)
        try:
            logger.info(f"Trying Voyager for: {profile_url}")
            result = await self.voyager.get_profile(profile_url)
            logger.info("Voyager succeeded")
            return result
        except Exception as e:
            logger.warning(f"Voyager failed: {e}")

        # Strategy 2: Browser fallback (slower, resilient)
        try:
            logger.info(f"Falling back to browser for: {profile_url}")
            result = await self.browser.get_profile(profile_url)
            logger.info("Browser succeeded")
            return result
        except Exception as e:
            logger.error(f"All strategies failed: {e}")
            raise RuntimeError(f"All strategies failed. Last error: {e}")
```

### 6. `app/routes/profile.py` — API Endpoint

```python
import re
from fastapi import APIRouter, Query, HTTPException
from app.services.orchestrator import ProfileOrchestrator
from app.schemas import ProfileResponse, ErrorResponse

router = APIRouter(prefix="/api/v1", tags=["Profile"])
orchestrator = ProfileOrchestrator()

def validate_linkedin_url(url: str) -> str:
    pattern = r"https?://(www\.)?linkedin\.com/in/[\w\-]+"
    if not re.match(pattern, url):
        raise HTTPException(
            status_code=400,
            detail="Invalid LinkedIn URL. Expected: https://www.linkedin.com/in/username"
        )
    if not url.startswith("https"):
        url = url.replace("http://", "https://")
    return url

@router.get(
    "/profile",
    response_model=ProfileResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get LinkedIn Profile Data",
)
async def get_profile(
    url: str = Query(..., description="LinkedIn profile URL")
):
    url = validate_linkedin_url(url)
    try:
        return await orchestrator.get_profile(url)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 7. `app/main.py` — Application Entry Point

```python
import time
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routes.profile import router as profile_router
from app.config import settings

logging.basicConfig(level=settings.LOG_LEVEL)

app = FastAPI(
    title="LinkedIn Profile API",
    description="Accepts a LinkedIn profile URL, returns structured JSON.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    logging.info(f"{request.method} {request.url.path} → {response.status_code} ({time.time()-start:.2f}s)")
    return response

@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"success": False, "error": str(exc)})

app.include_router(profile_router)

@app.get("/", tags=["Health"])
async def health():
    return {"status": "ok", "service": "linkedin-profile-api"}
```

### 8. `requirements.txt`

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
httpx==0.27.0
pydantic==2.9.0
pydantic-settings==2.5.0
playwright==1.48.0
python-dotenv==1.0.1
```

### 9. `Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium && playwright install-deps
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 10. `render.yaml`

```yaml
services:
  - type: web
    name: linkedin-profile-api
    runtime: docker
    plan: free
    envVars:
      - key: LI_AT_COOKIE
        sync: false
      - key: JSESSIONID
        sync: false
```

---

## API Usage

**Request:**
```
GET /api/v1/profile?url=https://www.linkedin.com/in/williamhgates
```

**Response (200):**
```json
{
  "success": true,
  "profile_url": "https://www.linkedin.com/in/williamhgates",
  "full_name": "Bill Gates",
  "headline": "Co-chair, Bill & Melinda Gates Foundation",
  "location": "Seattle, Washington",
  "about": "Co-chair of the Bill & Melinda Gates Foundation...",
  "experience": [{"title": "Co-chair", "company": "Gates Foundation", ...}],
  "education": [{"school": "Harvard University", ...}],
  "skills": ["Public Speaking", "Strategy"],
  "source": "voyager"
}
```

---

## How to Get LinkedIn Cookies

1. Open Chrome → `linkedin.com` → log in
2. Press `F12` → **Application** tab → **Cookies** → `linkedin.com`
3. Copy `li_at` value → paste into `.env` as `LI_AT_COOKIE`
4. Copy `JSESSIONID` value (remove quotes) → paste as `JSESSIONID`

---

## Deployment (Render.com)

1. Push to public GitHub repo
2. Render.com → New → Web Service → connect repo
3. Render detects `Dockerfile` automatically
4. Add `LI_AT_COOKIE` and `JSESSIONID` as env vars in dashboard
5. Deploy → get free `https://your-app.onrender.com` URL

---

## Known Limitations

1. **Cookie Expiry**: `li_at` expires; must refresh manually
2. **Rate Limiting**: Random delays (2-5s) built in; still may get blocked at high volume
3. **DOM Changes**: Browser fallback CSS selectors may break on LinkedIn UI updates
4. **Render Cold Start**: Free tier sleeps after 15min; first request takes ~30-60s
5. **Incomplete Data**: Restricted profiles may return null fields
