"""
Voyager API Client — Primary scraping strategy.

This module talks directly to LinkedIn's internal Voyager API, which is the
same API that LinkedIn's own web frontend uses to render profile pages.

HOW IT WORKS:
  1. We send an authenticated GET request to:
     https://www.linkedin.com/voyager/api/identity/profiles/{public_id}/profileView
  2. We include the user's li_at cookie and a CSRF token in the headers.
  3. LinkedIn returns a "normalized" JSON blob containing:
     - "data": references and metadata
     - "included": a flat array of ALL entities (Profile, Position, Education, Skill, etc.)
  4. Each entity in "included" has a "$type" field that tells us what it is.
  5. We iterate through "included", filter by $type, and map to our Pydantic models.

AUTHENTICATION HEADERS REQUIRED:
  - Cookie: li_at=<session_cookie>
  - Csrf-Token: <derived from JSESSIONID, or "ajax:0" as fallback>
  - Accept: application/vnd.linkedin.normalized+json+2.1
  - X-Restli-Protocol-Version: 2.0.0
"""

from __future__ import annotations

import asyncio
import logging
import random

import httpx

from app.config import settings
from app.schemas import (
    Certification,
    Education,
    Experience,
    Language,
    ProfileResponse,
)
from app.utils.parsing import extract_public_id, format_voyager_date

logger = logging.getLogger(__name__)


class VoyagerClient:
    """
    Async client that fetches LinkedIn profile data via the Voyager API.

    Usage:
        client = VoyagerClient()
        profile = await client.get_profile("https://www.linkedin.com/in/john-doe")
    """

    BASE_URL = "https://www.linkedin.com/voyager/api"

    def __init__(self) -> None:
        # Derive CSRF token from JSESSIONID cookie.
        # LinkedIn expects the JSESSIONID value without surrounding quotes.
        csrf = settings.JSESSIONID.strip('"') if settings.JSESSIONID else "ajax:0"

        self.headers = {
            # Mimic a real Chrome browser user-agent
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            # This Accept header is CRITICAL — it tells LinkedIn to return
            # the normalized JSON format with the "included" array.
            "Accept": "application/vnd.linkedin.normalized+json+2.1",
            # Required protocol version for the Voyager API
            "X-Restli-Protocol-Version": "2.0.0",
            # CSRF token derived from JSESSIONID
            "Csrf-Token": csrf,
        }

        # Session cookies — li_at is the main authentication cookie
        self.cookies: dict[str, str] = {"li_at": settings.LI_AT_COOKIE}
        if settings.JSESSIONID:
            self.cookies["JSESSIONID"] = settings.JSESSIONID

    async def get_profile(self, profile_url: str) -> ProfileResponse:
        """
        Fetch and parse a LinkedIn profile.

        Args:
            profile_url: Full LinkedIn profile URL
                         (e.g., "https://www.linkedin.com/in/john-doe")

        Returns:
            ProfileResponse with all available profile data.

        Raises:
            httpx.HTTPStatusError: If LinkedIn returns a non-2xx status.
            ValueError: If the URL is invalid.
        """
        public_id = extract_public_id(profile_url)
        logger.info(f"Voyager: fetching profile for public_id='{public_id}'")

        # Random delay to mimic human browsing patterns.
        # This is important — fixed intervals trigger bot detection.
        delay = random.uniform(settings.REQUEST_DELAY_MIN, settings.REQUEST_DELAY_MAX)
        await asyncio.sleep(delay)

        async with httpx.AsyncClient(
            headers=self.headers,
            cookies=self.cookies,
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            url = f"{self.BASE_URL}/identity/profiles/{public_id}/profileView"
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        return self._parse_profile_response(data, profile_url)

    def _parse_profile_response(
        self, data: dict, profile_url: str
    ) -> ProfileResponse:
        """
        Parse the raw Voyager API JSON into our ProfileResponse schema.

        The Voyager response structure looks like:
        {
          "data": { ... top-level references ... },
          "included": [
            {
              "$type": "com.linkedin.voyager.identity.profile.Profile",
              "firstName": "John",
              "lastName": "Doe",
              "headline": "Software Engineer",
              "locationName": "San Francisco",
              "summary": "About me text...",
              ...
            },
            {
              "$type": "com.linkedin.voyager.identity.profile.Position",
              "title": "Senior Engineer",
              "companyName": "Google",
              "locationName": "Mountain View",
              "timePeriod": {"startDate": {"month": 1, "year": 2020}, "endDate": null},
              ...
            },
            ... more entities ...
          ]
        }

        We iterate through "included" and dispatch based on "$type".
        """
        included: list[dict] = data.get("included", [])

        # --- Extract main Profile entity ---
        profile: dict = {}
        for item in included:
            type_str = item.get("$type", "")
            if type_str.endswith(".Profile") or type_str.endswith("profile.Profile"):
                profile = item
                break

        # --- Extract Experience (Position entities) ---
        experiences: list[Experience] = []
        for item in included:
            type_str = item.get("$type", "")
            if "Position" in type_str and item.get("title"):
                time_period = item.get("timePeriod") or {}
                experiences.append(
                    Experience(
                        title=item.get("title"),
                        company=item.get("companyName"),
                        company_logo_url=self._extract_logo_url(item),
                        location=item.get("locationName"),
                        description=item.get("description"),
                        start_date=format_voyager_date(
                            time_period.get("startDate")
                        ),
                        end_date=format_voyager_date(
                            time_period.get("endDate")
                        ),
                    )
                )

        # --- Extract Education ---
        educations: list[Education] = []
        for item in included:
            type_str = item.get("$type", "")
            if "Education" in type_str and item.get("schoolName"):
                time_period = item.get("timePeriod") or {}
                start_date = time_period.get("startDate") or {}
                end_date = time_period.get("endDate") or {}
                educations.append(
                    Education(
                        school=item.get("schoolName"),
                        school_logo_url=self._extract_logo_url(item),
                        degree=item.get("degreeName"),
                        field_of_study=item.get("fieldOfStudy"),
                        description=item.get("description"),
                        start_year=(
                            str(start_date["year"])
                            if start_date.get("year")
                            else None
                        ),
                        end_year=(
                            str(end_date["year"])
                            if end_date.get("year")
                            else None
                        ),
                    )
                )

        # --- Extract Skills ---
        skills: list[str] = []
        for item in included:
            type_str = item.get("$type", "")
            if "Skill" in type_str and item.get("name"):
                skills.append(item["name"])

        # --- Extract Certifications ---
        certifications: list[Certification] = []
        for item in included:
            type_str = item.get("$type", "")
            if "Certification" in type_str and item.get("name"):
                certifications.append(
                    Certification(
                        name=item.get("name"),
                        issuing_organization=item.get("authority"),
                        issue_date=format_voyager_date(
                            (item.get("timePeriod") or {}).get("startDate")
                        ),
                        credential_url=item.get("url"),
                    )
                )

        # --- Extract Languages ---
        languages: list[Language] = []
        for item in included:
            type_str = item.get("$type", "")
            if "Language" in type_str and item.get("name"):
                languages.append(
                    Language(
                        name=item.get("name"),
                        proficiency=item.get("proficiency"),
                    )
                )

        # --- Extract Profile Picture ---
        profile_image_url = self._extract_profile_picture(included)

        # --- Extract Background Image ---
        background_image_url = self._extract_background_image(included)

        # --- Build full name ---
        first = profile.get("firstName", "")
        last = profile.get("lastName", "")
        full_name = f"{first} {last}".strip() or None

        return ProfileResponse(
            profile_url=profile_url,
            first_name=first or None,
            last_name=last or None,
            full_name=full_name,
            headline=profile.get("headline"),
            location=profile.get("locationName"),
            about=profile.get("summary"),
            profile_image_url=profile_image_url,
            background_image_url=background_image_url,
            connections_count=self._extract_connections(included),
            experience=experiences,
            education=educations,
            skills=skills,
            certifications=certifications,
            languages=languages,
            source="voyager",
        )

    def _extract_profile_picture(self, included: list[dict]) -> str | None:
        """
        Extract the highest-resolution profile picture URL.

        Profile pictures in Voyager responses are stored as "vectorImage" objects
        with multiple "artifacts" at different resolutions. We pick the largest.
        """
        for item in included:
            type_str = str(item.get("$type", ""))
            if "ProfilePicture" not in type_str:
                continue
            ref = item.get("displayImageReference") or {}
            vector = ref.get("vectorImage") or {}
            artifacts = vector.get("artifacts", [])
            if not artifacts:
                continue
            root_url = vector.get("rootUrl", "")
            # Pick the artifact with the largest width
            largest = max(artifacts, key=lambda a: a.get("width", 0))
            segment = largest.get("fileIdentifyingUrlPathSegment", "")
            if root_url and segment:
                return root_url + segment
        return None

    def _extract_background_image(self, included: list[dict]) -> str | None:
        """Extract background/cover image URL if available."""
        for item in included:
            type_str = str(item.get("$type", ""))
            if "BackgroundImage" not in type_str and "backgroundImage" not in str(item):
                continue
            ref = item.get("displayImageReference") or item.get("backgroundImage") or {}
            vector = ref.get("vectorImage") or {}
            artifacts = vector.get("artifacts", [])
            if not artifacts:
                continue
            root_url = vector.get("rootUrl", "")
            largest = max(artifacts, key=lambda a: a.get("width", 0))
            segment = largest.get("fileIdentifyingUrlPathSegment", "")
            if root_url and segment:
                return root_url + segment
        return None

    def _extract_connections(self, included: list[dict]) -> str | None:
        """Extract connections count from the network info entity."""
        for item in included:
            type_str = str(item.get("$type", ""))
            if "NetworkInfo" in type_str:
                count = item.get("connectionsCount")
                if count is not None:
                    return str(count)
                # Some responses have "followersCount" instead
                followers = item.get("followersCount")
                if followers is not None:
                    return str(followers)
        return None

    def _extract_logo_url(self, item: dict) -> str | None:
        """Extract company/school logo URL from an entity if available."""
        logo = item.get("companyLogo") or item.get("schoolLogo") or item.get("logo")
        if not logo:
            return None
        vector = logo.get("vectorImage") or {}
        artifacts = vector.get("artifacts", [])
        if not artifacts:
            return None
        root_url = vector.get("rootUrl", "")
        largest = max(artifacts, key=lambda a: a.get("width", 0))
        segment = largest.get("fileIdentifyingUrlPathSegment", "")
        return (root_url + segment) if (root_url and segment) else None
