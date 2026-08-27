"""
Profile API route — the single endpoint that powers the entire API.

GET /api/v1/profile?url=https://www.linkedin.com/in/username

This endpoint:
  1. Validates the incoming LinkedIn URL
  2. Delegates to the ProfileOrchestrator (Voyager → Browser waterfall)
  3. Returns structured JSON matching the ProfileResponse schema
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ErrorResponse, ProfileResponse
from app.services.orchestrator import ProfileOrchestrator

router = APIRouter(prefix="/api/v1", tags=["Profile"])

# Single orchestrator instance — reused across all requests
orchestrator = ProfileOrchestrator()


def validate_linkedin_url(url: str) -> str:
    """
    Validate that the input is a real LinkedIn profile URL.

    Accepted formats:
      - https://www.linkedin.com/in/john-doe
      - https://linkedin.com/in/john-doe-123
      - http://www.linkedin.com/in/jane  (upgraded to HTTPS)

    Rejected:
      - https://www.linkedin.com/company/google  (not a profile)
      - https://www.google.com  (not LinkedIn)
      - random text

    Returns the normalized URL (HTTPS, trimmed).
    Raises HTTPException 400 on invalid input.
    """
    url = url.strip()
    pattern = r"^https?://(www\.)?linkedin\.com/in/[\w\-]+"
    if not re.match(pattern, url):
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid LinkedIn profile URL. "
                "Expected format: https://www.linkedin.com/in/username"
            ),
        )
    # Upgrade HTTP to HTTPS
    if url.startswith("http://"):
        url = url.replace("http://", "https://", 1)
    return url


@router.get(
    "/profile",
    response_model=ProfileResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid LinkedIn URL"},
        500: {"model": ErrorResponse, "description": "Scraping failed"},
    },
    summary="Get LinkedIn Profile Data",
    description=(
        "Accepts a LinkedIn profile URL and returns structured profile data "
        "including name, headline, location, about, experience, education, "
        "skills, certifications, languages, and profile images."
    ),
)
async def get_profile(
    url: str = Query(
        ...,
        description="LinkedIn profile URL (e.g., https://www.linkedin.com/in/williamhgates)",
        examples=["https://www.linkedin.com/in/williamhgates"],
    ),
) -> ProfileResponse:
    """
    Main API endpoint. Validates the URL, then delegates to the orchestrator.
    """
    # Step 1: Validate input
    url = validate_linkedin_url(url)

    # Step 2: Scrape (Voyager first, then browser fallback)
    try:
        return await orchestrator.get_profile(url)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
