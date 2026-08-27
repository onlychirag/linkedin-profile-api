import os
from typing import List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

app = FastAPI(
    title="LinkedIn Profile API",
    description="Cookie-free LinkedIn profile enrichment API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROXYCURL_API_KEY = os.getenv("PROXYCURL_API_KEY")
PROXYCURL_URL = "https://nubela.co/proxycurl/api/v2/linkedin"


# --- Response Models ---

class Experience(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class Education(BaseModel):
    school: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class Certification(BaseModel):
    name: Optional[str] = None
    authority: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ProfileResponse(BaseModel):
    name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    about: Optional[str] = None
    experience: List[Experience] = []
    education: List[Education] = []
    skills: List[str] = []
    certifications: List[Certification] = []
    languages: List[str] = []
    profile_image: Optional[str] = None


# --- Endpoints ---

@app.get("/api/profile", response_model=ProfileResponse)
async def get_profile(url: str = Query(..., description="Full LinkedIn profile URL")):
    """
    Fetch a LinkedIn profile by URL and return structured data.
    No browser cookies or session auth required.
    """
    if not PROXYCURL_API_KEY:
        raise HTTPException(status_code=500, detail="PROXYCURL_API_KEY not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            PROXYCURL_URL,
            headers={"Authorization": f"Bearer {PROXYCURL_API_KEY}"},
            params={"url": url, "fallback_to_cache": "on-error"},
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text,
        )

    data = response.json()

    return ProfileResponse(
        name=data.get("full_name"),
        headline=data.get("occupation"),
        location=f"{data.get('city', '')}, {data.get('state', '')}, {data.get('country', '')}".strip(", "),
        about=data.get("summary"),
        experience=[
            Experience(
                title=exp.get("title"),
                company=exp.get("company"),
                location=exp.get("location"),
                start_date=_fmt_date(exp.get("starts_at")),
                end_date=_fmt_date(exp.get("ends_at")),
                description=exp.get("description"),
            )
            for exp in data.get("experiences", [])
        ],
        education=[
            Education(
                school=edu.get("school"),
                degree=edu.get("degree_name"),
                field_of_study=edu.get("field_of_study"),
                start_date=_fmt_date(edu.get("starts_at")),
                end_date=_fmt_date(edu.get("ends_at")),
            )
            for edu in data.get("education", [])
        ],
        skills=data.get("skills", []),
        certifications=[
            Certification(
                name=cert.get("name"),
                authority=cert.get("authority"),
                start_date=_fmt_date(cert.get("starts_at")),
                end_date=_fmt_date(cert.get("ends_at")),
            )
            for cert in data.get("certifications", [])
        ],
        languages=data.get("languages", []),
        profile_image=data.get("profile_pic_url"),
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


# --- Helpers ---

def _fmt_date(date_dict) -> Optional[str]:
    if not date_dict:
        return None
    year = date_dict.get("year")
    month = date_dict.get("month")
    day = date_dict.get("day")
    parts = [p for p in [year, month, day] if p]
    return "-".join(str(p) for p in parts) if parts else None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
