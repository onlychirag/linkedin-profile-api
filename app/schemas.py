"""
Pydantic v2 response models for the LinkedIn Profile API.

Every field is Optional because LinkedIn profiles have variable completeness —
some users don't list skills, others have no certifications, etc.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Experience(BaseModel):
    """A single work experience entry."""

    title: Optional[str] = None
    company: Optional[str] = None
    company_logo_url: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None  # e.g. "Jan 2020"
    end_date: Optional[str] = None  # e.g. "Present" or "Dec 2023"
    duration: Optional[str] = None  # e.g. "3 yrs 2 mos"
    description: Optional[str] = None


class Education(BaseModel):
    """A single education entry."""

    school: Optional[str] = None
    school_logo_url: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[str] = None
    end_year: Optional[str] = None
    description: Optional[str] = None


class Certification(BaseModel):
    """A single certification entry."""

    name: Optional[str] = None
    issuing_organization: Optional[str] = None
    issue_date: Optional[str] = None
    credential_url: Optional[str] = None


class Language(BaseModel):
    """A single language entry."""

    name: Optional[str] = None
    proficiency: Optional[str] = None


class ProfileResponse(BaseModel):
    """
    The top-level API response for a successful profile scrape.

    'source' indicates which strategy succeeded:
      - "voyager"  → Data came from LinkedIn's internal Voyager API
      - "browser"  → Data came from Playwright DOM scraping
    """

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
    """Returned on 4xx / 5xx errors."""

    success: bool = False
    error: str
    detail: Optional[str] = None
