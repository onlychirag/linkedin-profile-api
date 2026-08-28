from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ProfileImage(BaseModel):
    url: str
    width: int | None = None
    height: int | None = None
    source: str | None = None


class ExperienceItem(BaseModel):
    title: str | None = None
    company: str | None = None
    employment_type: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration: str | None = None
    location: str | None = None
    description: list[str] = Field(default_factory=list)
    source_text: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    school: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: list[str] = Field(default_factory=list)
    source_text: list[str] = Field(default_factory=list)


class SkillItem(BaseModel):
    name: str
    context: list[str] = Field(default_factory=list)
    source_text: list[str] = Field(default_factory=list)


class CertificationItem(BaseModel):
    name: str | None = None
    issuer: str | None = None
    issue_date: str | None = None
    expiration_date: str | None = None
    credential_id: str | None = None
    credential_url: str | None = None
    source_text: list[str] = Field(default_factory=list)


class LanguageItem(BaseModel):
    name: str
    proficiency: str | None = None
    source_text: list[str] = Field(default_factory=list)


class ExtractionMetadata(BaseModel):
    requested_url: str
    resolved_url: str | None = None
    public_identifier: str | None = None
    authenticated: bool = False
    strategies: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LinkedInProfile(BaseModel):
    profile_url: str
    public_identifier: str
    name: str | None = None
    headline: str | None = None
    location: str | None = None
    about: str | None = None
    profile_images: list[ProfileImage] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    skills: list[SkillItem] = Field(default_factory=list)
    certifications: list[CertificationItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    raw_sections: dict[str, Any] = Field(default_factory=dict)
    extraction: ExtractionMetadata
