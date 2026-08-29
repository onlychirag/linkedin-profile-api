from __future__ import annotations

import json
import re
from typing import Any, Iterable
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup, Tag

from app.errors import InvalidLinkedInUrl
from app.models import (
    CertificationItem,
    EducationItem,
    ExperienceItem,
    ExtractionMetadata,
    LanguageItem,
    LinkedInProfile,
    ProfileImage,
    SkillItem,
)

DETAIL_SECTIONS = ("experience", "education", "skills", "certifications", "languages")

MONTH_PATTERN = (
    r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|"
    r"January|February|March|April|June|July|August|September|October|November|December"
)
DATE_RE = re.compile(rf"(({MONTH_PATTERN})\s+)?\d{{4}}|Present", re.IGNORECASE)
DATE_RANGE_RE = re.compile(
    rf"(({MONTH_PATTERN})\s+)?\d{{4}}\s*(-|to)\s*((({MONTH_PATTERN})\s+)?\d{{4}}|Present)|\d{{4}}",
    re.IGNORECASE,
)

NOISE = {
    "",
    "about",
    "activity",
    "analytics",
    "certifications",
    "contact info",
    "education",
    "experience",
    "featured",
    "followers",
    "join now",
    "languages",
    "licenses & certifications",
    "licenses and certifications",
    "loading",
    "people also viewed",
    "recommendations",
    "show all",
    "show less",
    "show more",
    "sign in",
    "skills",
    "skip to main content",
}


def normalize_linkedin_profile_url(raw_url: str) -> tuple[str, str]:
    value = raw_url.strip()
    if not value:
        raise InvalidLinkedInUrl("URL is required")
    if "://" not in value:
        value = f"https://{value}"

    parsed = urlparse(value)
    host = parsed.hostname.lower() if parsed.hostname else ""
    if not (host == "linkedin.com" or host.endswith(".linkedin.com")):
        raise InvalidLinkedInUrl("Only linkedin.com profile URLs are supported")

    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0].lower() not in {"in", "pub"}:
        raise InvalidLinkedInUrl("Expected a LinkedIn /in/{id}/ or /pub/{id}/ URL")

    public_identifier = parts[1].strip()
    if not re.fullmatch(r"[A-Za-z0-9_.%-]+", public_identifier):
        raise InvalidLinkedInUrl("LinkedIn public identifier contains unsupported characters")

    canonical = f"https://www.linkedin.com/{parts[0].lower()}/{public_identifier}/"
    return canonical, public_identifier


def clean_text(value: str | None) -> str:
    if value is None:
        return ""
    value = (
        value.replace("\xa0", " ")
        .replace("\u200b", "")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    return re.sub(r"\s+", " ", value).strip()


def visible_lines(element: Tag) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for raw in element.stripped_strings:
        line = clean_text(raw)
        key = line.lower()
        if not line or key in NOISE:
            continue
        if set(line) <= {"*"}:
            continue
        if key.endswith(" logo") or key.endswith(" image"):
            continue
        if key in seen:
            continue
        seen.add(key)
        lines.append(line)
    return lines


def parse_profile_html(html: str, requested_url: str, resolved_url: str | None = None) -> LinkedInProfile:
    profile_url, public_identifier = normalize_linkedin_profile_url(requested_url)
    soup = BeautifulSoup(html, "html.parser")
    person = _find_jsonld_person(soup)
    meta = _meta_tags(soup)
    title_name, title_headline = _parse_title(meta.get("og:title") or meta.get("title"))

    name = _first_present(
        _string_from_json(person.get("name")),
        _selector_text(soup, "h1.text-heading-xlarge"),
        _selector_text(soup, "h1.top-card-layout__title"),
        _selector_text(soup, "main h1"),
        title_name,
    )
    location = _first_present(
        _address_from_json(person.get("address")),
        _selector_text(soup, ".top-card__subline-item"),
        _selector_text(soup, ".text-body-small.inline.t-black--light.break-words"),
        _profile_location_from_body_lines(soup, name),
        _best_location_line(soup),
    )
    
    og_desc = meta.get("og:description") or meta.get("description")
    
    headline = _first_present(
        _string_from_json(person.get("jobTitle")),
        _selector_text(soup, ".text-body-medium.break-words"),
        _selector_text(soup, ".top-card-layout__headline"),
        _extract_meta_headline(og_desc),
        title_headline,
        _extract_headline_from_text(soup, title_name),
    )
    
    about = _first_present(
        _extract_about(soup),
        _extract_meta_about(og_desc),
        _extract_about_from_text(soup)
    )
    images = _extract_images(soup, person, meta, name)

    strategies = ["public-metadata"] if (person or meta) else ["html-dom"]
    return LinkedInProfile(
        profile_url=profile_url,
        public_identifier=public_identifier,
        name=name,
        headline=headline,
        location=location,
        about=about,
        profile_images=images,
        extraction=ExtractionMetadata(
            requested_url=requested_url,
            resolved_url=resolved_url or profile_url,
            public_identifier=public_identifier,
            strategies=strategies,
        ),
    )


def parse_detail_section_html(html: str, section: str) -> list[Any]:
    soup = BeautifulSoup(html, "html.parser")
    full_text = soup.get_text("\n")
    if _section_is_empty(full_text, section):
        return []
    groups = [
        _trim_detail_group_lines(lines)
        for lines in _candidate_item_lines(soup)
        if _looks_like_detail_group(_trim_detail_group_lines(lines), section)
    ]
    if not groups:
        return parse_detail_section_text(full_text, section)
    if section == "experience":
        return [_parse_experience(lines) for lines in groups if lines]
    if section == "education":
        return [_parse_education(lines) for lines in groups if lines]
    if section == "skills":
        return [_parse_skill(lines) for lines in groups if lines and _looks_like_skill(lines)]
    if section == "certifications":
        return [_parse_certification(lines) for lines in groups if lines]
    if section == "languages":
        return [_parse_language(lines) for lines in groups if lines and len(lines[0]) <= 80]
    return []


def parse_detail_section_text(text: str, section: str) -> list[Any]:
    groups = _text_detail_groups(text, section)
    if section == "experience":
        return [_parse_experience(lines) for lines in groups if lines]
    if section == "education":
        return [_parse_education(lines) for lines in groups if lines]
    if section == "skills":
        return [_parse_skill(lines) for lines in groups if lines and _looks_like_skill(lines)]
    if section == "certifications":
        return [_parse_certification(lines) for lines in groups if lines]
    if section == "languages":
        return [_parse_language(lines) for lines in groups if lines and len(lines[0]) <= 80]
    return []


def parse_compact_profile_education(
    html: str,
    name: str | None = None,
    location: str | None = None,
    companies: Iterable[str | None] = (),
) -> list[EducationItem]:
    soup = BeautifulSoup(html, "html.parser")
    lines = _plain_lines(soup.get_text("\n"))
    if not lines:
        return []

    school = _compact_profile_school(lines, name, location, companies)
    try:
        start = next(index for index, line in enumerate(lines) if line.lower() == "education")
    except StopIteration:
        return []

    stop_lines = {
        "accomplishments",
        "certification",
        "contact",
        "languages",
        "organizations",
        "projects",
        "recommendations",
        "skills",
        "volunteer experience",
    }
    body: list[str] = []
    for line in lines[start + 1 :]:
        lower = line.lower()
        if lower in stop_lines:
            break
        if lower == "add education":
            continue
        if lower.startswith("have more education"):
            continue
        if "profile views" in lower:
            continue
        if _is_detail_text_noise(line, "education"):
            continue
        body.append(line)

    dates: list[str] = []
    text_lines: list[str] = []
    for line in body:
        if _is_date_line(line):
            dates.append(line)
        elif len(line) <= 120:
            text_lines.append(line)

    if text_lines and _looks_like_school_line(text_lines[0]):
        school = text_lines[0]
        degree = text_lines[1] if len(text_lines) > 1 else None
        field = text_lines[2] if len(text_lines) > 2 else None
    else:
        if not school and text_lines:
            school = text_lines.pop(0)
        degree = text_lines[0] if text_lines else None
        field = text_lines[1] if len(text_lines) > 1 else None
    if not any((school, degree, field, dates)):
        return []

    return [
        EducationItem(
            school=school,
            degree=degree,
            field_of_study=field,
            start_date=dates[0] if dates else None,
            end_date=dates[1] if len(dates) > 1 else None,
            source_text=body,
        )
    ]


def merge_profiles(primary: LinkedInProfile, fallback: LinkedInProfile) -> LinkedInProfile:
    merged = primary.model_copy(deep=True)
    for field in ("name", "headline", "location", "about"):
        if not getattr(merged, field) and getattr(fallback, field):
            setattr(merged, field, getattr(fallback, field))

    for field in ("profile_images", "experience", "education", "skills", "certifications", "languages"):
        if not getattr(merged, field) and getattr(fallback, field):
            setattr(merged, field, getattr(fallback, field))

    merged.raw_sections = {**fallback.raw_sections, **merged.raw_sections}
    merged.extraction.strategies = _dedupe(
        [*fallback.extraction.strategies, *merged.extraction.strategies]
    )
    merged.extraction.warnings = _dedupe(
        [*fallback.extraction.warnings, *merged.extraction.warnings]
    )
    merged.extraction.authenticated = (
        merged.extraction.authenticated or fallback.extraction.authenticated
    )
    return merged


def profile_has_core_data(profile: LinkedInProfile) -> bool:
    return bool(profile.name or profile.headline or profile.about or profile.experience)


def _candidate_item_lines(soup: BeautifulSoup) -> list[list[str]]:
    selectors = [
        ".pvs-entity",
        "li.pvs-list__paged-list-item",
        "li.artdeco-list__item",
        "li.experience-item",
        "li.education__list-item",
        "li.profile-section-card",
    ]
    return _collect_item_lines(soup, selectors)


def _collect_item_lines(soup: BeautifulSoup, selectors: list[str]) -> list[list[str]]:
    groups: list[list[str]] = []
    seen: set[str] = set()
    for selector in selectors:
        for item in soup.select(selector):
            lines = visible_lines(item)
            if not lines:
                continue
            key = "\n".join(lines[:12]).lower()
            if key in seen:
                continue
            if len(" ".join(lines)) < 3:
                continue
            seen.add(key)
            groups.append(lines[:30])
    return groups[:80]


def _looks_like_detail_group(lines: list[str], section: str) -> bool:
    if not lines:
        return False
    if len(lines) == 1 and section in {"experience", "education", "certifications"}:
        return False

    joined = " ".join(lines).lower()
    blocked_fragments = (
        "ad options",
        "courses",
        "course",
        "hide or report this ad",
        "i don't want to see this ad",
        "manage your ad preferences",
        "open to work",
        "professional community policies",
        "report this ad",
        "why am i seeing this ad",
        "linkedin community",
        "explore more",
        "let the right people know",
        "conversations today",
        "stay up to date",
        "more profiles for you",
    )
    if any(fragment in joined for fragment in blocked_fragments):
        return False

    if section in {"experience", "education"}:
        return any(_is_date_line(line) for line in lines)
    if section == "certifications":
        return len(lines) >= 2
    if section in {"skills", "languages"}:
        return len(lines[0]) <= 100 and _looks_like_skill(lines)
    return True


def _text_detail_groups(text: str, section: str) -> list[list[str]]:
    lines = _section_body_lines(text, section)
    if not lines or _empty_section(lines, section):
        return []
    if section in {"experience", "education"}:
        return _groups_around_dates(lines)
    if section == "certifications":
        return _groups_around_dates(lines) or ([lines] if len(lines) >= 2 else [])
    if section == "languages":
        grouped = []
        proficiencies = {"native or bilingual proficiency", "full professional proficiency", "professional working proficiency", "limited working proficiency", "elementary proficiency"}
        i = 0
        while i < len(lines):
            line = lines[i]
            if len(line) <= 100:
                if i + 1 < len(lines) and lines[i+1].lower() in proficiencies:
                    grouped.append([line, lines[i+1]])
                    i += 2
                else:
                    grouped.append([line])
                    i += 1
            else:
                i += 1
        return grouped
    if section == "skills":
        return [[line] for line in lines if len(line) <= 100]
    return []


def _section_body_lines(text: str, section: str) -> list[str]:
    titles = {
        "experience": {"experience"},
        "education": {"education"},
        "skills": {"skills"},
        "certifications": {"licenses & certifications", "licenses and certifications", "certifications"},
        "languages": {"languages"},
    }
    stop_lines = {
        "about",
        "accessibility",
        "activity",
        "ad choices",
        "advertising",
        "careers",
        "community guidelines",
        "contact info",
        "learning",
        "mobile",
        "privacy & terms",
        "profile language",
        "questions?",
        "recommendation transparency",
        "sales solutions",
        "select language",
        "small business",
        "talent solutions",
        "who your viewers also viewed",
        "more profiles for you",
    }
    raw_lines = _plain_lines(text)
    start = None
    for index, line in enumerate(raw_lines):
        if line.lower() in titles.get(section, set()):
            start = index + 1
            break
    if start is None:
        return []

    body: list[str] = []
    for line in raw_lines[start:]:
        lower = line.lower()
        if lower in stop_lines or lower.startswith("who your viewers"):
            break
        if _is_detail_text_noise(line, section):
            continue
        body.append(line)
    return body


def _plain_lines(text: str) -> list[str]:
    lines: list[str] = []
    seen_run: set[str] = set()
    for raw in text.splitlines():
        line = clean_text(raw)
        lower = line.lower()
        if not line or lower in seen_run:
            continue
        seen_run.add(lower)
        lines.append(line)
    return lines


def _is_detail_text_noise(line: str, section: str) -> bool:
    lower = line.lower()
    noise = NOISE | {
        ".",
        "\u00b7",
        "ad options",
        "add licenses or certifications",
        "add languages",
        "add section",
        "add skills",
        "all",
        "don't want to see this",
        "enhance profile",
        "enhance with ai",
        "for business",
        "hide or report this ad",
        "home",
        "i don't want to see this ad in my feed",
        "i've seen the same ad too often",
        "industry knowledge",
        "interpersonal skills",
        "jobs",
        "manage your ad preferences",
        "me",
        "more profiles for you",
        "open to",
        "private to you",
        "report this ad",
        "resources",
        "show details",
        "showcase your skills and strengths.",
        "submit",
        "tell us why you don't want to see this",
        "tools & technologies",
        "it's annoying or not interesting",
        "if you think this goes against our professional community policies, please let us know.",
        "why am i seeing this ad?",
        "your feedback will help us improve your experience",
    }
    if lower in noise:
        return True
    if lower.startswith("when you add new"):
        return True
    if lower.startswith("nothing to see"):
        return True
    if lower.startswith("tell us why"):
        return True
    if lower.startswith("if you think this goes against"):
        return True
    if "professional community policies" in lower:
        return True
    if "same ad too often" in lower or "annoying or not interesting" in lower:
        return True
    if lower.endswith("courses") or lower.endswith("course"):
        return True
    if re.fullmatch(r"\d+\s+notifications?", lower):
        return True
    if re.fullmatch(r"[\u00b7. ]*\d(?:st|nd|rd|th)?\+?", lower):
        return True
    if set(line) <= {"*"}:
        return True
    return False


def _empty_section(lines: list[str], section: str) -> bool:
    return _section_is_empty("\n".join(lines), section)


def _section_is_empty(text: str, section: str) -> bool:
    joined = clean_text(text).lower()
    empty_markers = {
        "skills": (
            "when you add new skills they'll show up here",
            "when you add new skills theyll show up here",
            "showcase your skills and strengths",
        ),
        "certifications": (
            "nothing to see for now",
            "when you add new licenses & certifications they'll show up here",
            "when you add new licenses and certifications they'll show up here",
        ),
        "languages": (
            "nothing to see for now",
            "when you add new languages they'll show up here",
        ),
    }
    return any(marker in joined for marker in empty_markers.get(section, ()))


def _groups_around_dates(lines: list[str]) -> list[list[str]]:
    date_indexes = [index for index, line in enumerate(lines) if _is_date_line(line)]
    groups: list[list[str]] = []
    next_start = 0
    for position, date_index in enumerate(date_indexes):
        start = max(next_start, date_index - 2)
        if position + 1 < len(date_indexes):
            end = max(date_index + 1, date_indexes[position + 1] - 2)
        else:
            end = len(lines)
        group = lines[start:end]
        if group:
            groups.append(group)
        next_start = end
    return groups


def _trim_detail_group_lines(lines: list[str]) -> list[str]:
    stop_markers = {
        "more profiles for you",
        "people also viewed",
        "people you may know",
        "who your viewers also viewed",
    }
    trimmed: list[str] = []
    for line in lines:
        if line.lower() in stop_markers:
            break
        trimmed.append(line)
    return trimmed


def _compact_profile_school(
    lines: list[str],
    name: str | None,
    location: str | None,
    companies: Iterable[str | None],
) -> str | None:
    if not name:
        return None
    company_names = {clean_text(company).lower() for company in companies if company}
    try:
        name_index = next(index for index, line in enumerate(lines) if line == name)
    except StopIteration:
        return None

    end = min(len(lines), name_index + 16)
    for index in range(name_index + 1, end):
        lower = lines[index].lower()
        if lines[index] == location or lower.endswith("area") or " connection" in lower:
            end = index
            break

    skip = {
        ".",
        "joined 2018",
        "joined 2019",
        "joined 2020",
        "joined 2021",
        "joined 2022",
        "joined 2023",
        "premium member",
        "share profile",
    }
    for line in lines[name_index + 1 : end]:
        lower = line.lower()
        if lower in skip or lower in company_names or lower.startswith("joined "):
            continue
        if lower.endswith("member"):
            continue
        if set(line) <= {".", "\u00b7", "-"}:
            continue
        return line
    return None


def _looks_like_school_line(line: str) -> bool:
    lower = line.lower()
    return any(
        token in lower
        for token in (
            "academy",
            "college",
            "institute",
            "school",
            "university",
            "bits",
            "iit",
            "pilani",
            "roorkee",
        )
    )


def _parse_experience(lines: list[str]) -> ExperienceItem:
    lines = _normalize_experience_lines(lines)
    date_index = _first_index(lines, _is_date_line)
    company_line = _line_at(lines, 1 if date_index != 1 else 2)
    company, employment_type = _split_company_line(company_line)
    start_date, end_date, duration = _split_date_line(_line_at(lines, date_index))

    location = None
    if date_index is not None:
        for line in lines[date_index + 1 : date_index + 4]:
            if _looks_like_location(line):
                location = line
                break

    used = {0}
    if company_line:
        used.add(lines.index(company_line))
    if date_index is not None:
        used.add(date_index)
    if location and location in lines:
        used.add(lines.index(location))

    return ExperienceItem(
        title=_line_at(lines, 0),
        company=company,
        employment_type=employment_type,
        start_date=start_date,
        end_date=end_date,
        duration=duration,
        location=location,
        description=[line for index, line in enumerate(lines) if index not in used],
        source_text=lines,
    )


def _normalize_experience_lines(lines: list[str]) -> list[str]:
    if len(lines) < 3:
        return lines
    date_index = _first_index(lines, _is_date_line)
    if date_index == 2 and lines[0].lstrip().startswith("-") and not lines[1].lstrip().startswith("-"):
        return lines[1:]
    return lines


def _parse_education(lines: list[str]) -> EducationItem:
    date_index = _first_index(lines, _is_date_line)
    degree_line = _line_at(lines, 1 if date_index != 1 else 2)
    degree, field = _split_degree_line(degree_line)
    start_date, end_date, _duration = _split_date_line(_line_at(lines, date_index))
    used = {0}
    if degree_line:
        used.add(lines.index(degree_line))
    if date_index is not None:
        used.add(date_index)
    return EducationItem(
        school=_line_at(lines, 0),
        degree=degree,
        field_of_study=field,
        start_date=start_date,
        end_date=end_date,
        description=[line for index, line in enumerate(lines) if index not in used],
        source_text=lines,
    )


def _parse_skill(lines: list[str]) -> SkillItem:
    return SkillItem(name=lines[0], context=lines[1:], source_text=lines)


def _parse_certification(lines: list[str]) -> CertificationItem:
    issue = None
    expiration = None
    credential_id = None
    for line in lines:
        lower = line.lower()
        if lower.startswith("issued"):
            issue = line
        elif "expires" in lower:
            expiration = line
        elif "credential id" in lower:
            credential_id = line.split(":", 1)[-1].strip()
    return CertificationItem(
        name=_line_at(lines, 0),
        issuer=_line_at(lines, 1),
        issue_date=issue,
        expiration_date=expiration,
        credential_id=credential_id,
        source_text=lines,
    )


def _parse_language(lines: list[str]) -> LanguageItem:
    return LanguageItem(name=lines[0], proficiency=_line_at(lines, 1), source_text=lines)


def _looks_like_skill(lines: list[str]) -> bool:
    first = lines[0].lower()
    blocked = {
        "all",
        "ad options",
        "connect",
        "don't want to see this",
        "follow",
        "hide or report this ad",
        "i don't want to see this ad in my feed",
        "i've seen the same ad too often",
        "industry knowledge",
        "interpersonal skills",
        "jobs",
        "linkedin",
        "manage your ad preferences",
        "messaging",
        "more profiles for you",
        "my network",
        "notifications",
        "report this ad",
        "submit",
        "tell us why you don't want to see this",
        "tools & technologies",
        "it's annoying or not interesting",
        "if you think this goes against our professional community policies, please let us know.",
        "why am i seeing this ad?",
        "your feedback will help us improve your experience",
    }
    if first in blocked:
        return False
    return not any(
        fragment in first
        for fragment in (
            "get api for any ehr",
            "professional community policies",
            "same ad too often",
            "annoying or not interesting",
        )
    ) and len(lines[0]) <= 100


def _split_company_line(line: str | None) -> tuple[str | None, str | None]:
    if not line:
        return None, None
    parts = [part.strip() for part in re.split(r"\s+\u00b7\s+", line, maxsplit=1)]
    company = parts[0] or None
    employment_type = parts[1] if len(parts) > 1 else None
    return company, employment_type


def _split_degree_line(line: str | None) -> tuple[str | None, str | None]:
    if not line:
        return None, None
    if "," in line:
        degree, field = [part.strip() for part in line.split(",", 1)]
        return degree or None, field or None
    return line, None


def _split_date_line(line: str | None) -> tuple[str | None, str | None, str | None]:
    if not line:
        return None, None, None
    parts = [part.strip() for part in re.split(r"\s+\u00b7\s+", line)]
    range_part = parts[0]
    duration = parts[1] if len(parts) > 1 else None
    if " - " in range_part:
        start, end = [part.strip() for part in range_part.split(" - ", 1)]
    else:
        split = re.split(r"\s+to\s+", range_part, maxsplit=1, flags=re.IGNORECASE)
        start = split[0].strip() if split else range_part
        end = split[1].strip() if len(split) > 1 else None
    return start or None, end or None, duration


def _is_date_line(line: str) -> bool:
    if re.search(r"\d{5,}", line):
        return False
    return bool(DATE_RANGE_RE.search(line)) and any(char.isdigit() for char in line)


def _looks_like_location(line: str) -> bool:
    lower = line.lower()
    if any(token in lower for token in ("remote", "hybrid", "on-site", "onsite")):
        return True
    return "," in line and len(line) <= 90


def _extract_meta_headline(description: str | None) -> str | None:
    if not description:
        return None
    parts = description.split(" | ")
    for part in parts:
        if part.strip().startswith("Headline:"):
            return clean_text(part.replace("Headline:", "", 1))
    return None

def _extract_headline_from_text(soup: BeautifulSoup, name: str | None) -> str | None:
    if not name:
        return None
    
    full_text = soup.get_text('\n', strip=True)
    lines = [line.strip() for line in full_text.split('\n') if line.strip()]
    
    for i, line in enumerate(lines):
        if line.lower() == name.lower() and i + 1 < len(lines):
            # Scan the next 10 lines for the headline
            for j in range(1, 15):
                if i + j >= len(lines):
                    break
                next_line = lines[i + j]
                
                # Skip meaningless single characters or UI text
                if len(next_line) <= 1 or next_line.startswith('Verify'):
                    continue
                    
                # Skip action buttons on own profile
                if next_line in ("Resources", "Enhance profile", "Add section", "Open to", "Contact info", "Show all", "Share Profile"):
                    continue
                    
                # Skip if it's the name again
                if next_line.lower() == name.lower():
                    continue
                    
                # Skip if we reach a known section
                if next_line in ("Activity", "About", "Experience", "More profiles for you", "Premium member", "Show details", "Get started", "Add custom button"):
                    break
                
                # The first long-ish text is likely the headline!
                if len(next_line) > 5:
                    return next_line
                    
    return None

def _extract_meta_about(description: str | None) -> str | None:
    if not description:
        return None
    parts = description.split(" | ")
    for part in parts:
        if part.strip().startswith("About:"):
            return clean_text(part.replace("About:", "", 1))
    return None

def _extract_about_from_text(soup: BeautifulSoup) -> str | None:
    full_text = soup.get_text('\n', strip=True)
    lines = [line.strip() for line in full_text.split('\n') if line.strip()]
    
    for i, line in enumerate(lines):
        if line == 'About' and i + 1 < len(lines):
            next_line = lines[i + 1]
            # Make sure it's not the footer About
            if next_line in ("Accessibility", "Talent Solutions", "Help Center", "Privacy & Terms", "Community Guidelines"):
                continue
            
            # If the next line is long, it's the about section
            if len(next_line) > 10:
                # Let's collect up to the next section
                about_lines = []
                for j in range(i + 1, len(lines)):
                    if lines[j] in ("Experience", "Education", "Skills", "Activity", "Featured", "More profiles for you", "Top skills"):
                        break
                    about_lines.append(lines[j])
                return clean_text(' '.join(about_lines))
    return None

def _extract_about(soup: BeautifulSoup) -> str | None:
    anchors = soup.select("#about")
    for anchor in anchors:
        section = anchor.find_parent("section")
        if not section:
            continue
        lines = [line for line in visible_lines(section) if line.lower() != "about"]
        long_lines = [line for line in lines if len(line) > 25]
        if long_lines:
            return max(long_lines, key=len)
            
    # Try the newer structured about section format
    about_card = soup.find("div", {"id": "about"})
    if not about_card:
        for card in soup.select("section.artdeco-card"):
            heading = card.find(["h2", "h3"])
            if heading and "about" in heading.get_text().strip().lower():
                about_card = card
                break

    if about_card:
        text_container = about_card.select_one(
            ".inline-show-more-text, .display-flex.ph5.pv3 .visually-hidden"
        )
        if text_container:
            text = text_container.get_text(separator="\n").strip()
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            filtered = [
                line
                for line in lines
                if not line.lower().startswith("see more")
                and not line.lower().startswith("show less")
            ]
            if filtered:
                return "\n".join(filtered)
                
    return None


def _extract_images(
    soup: BeautifulSoup,
    person: dict[str, Any],
    meta: dict[str, str],
    profile_name: str | None = None,
) -> list[ProfileImage]:
    images: list[ProfileImage] = []
    for value, source in (
        (person.get("image"), "json-ld"),
        (meta.get("og:image"), "open-graph"),
    ):
        for url in _image_urls(value):
            images.append(ProfileImage(url=url, source=source))

    for image in soup.select(
        "img.pv-top-card-profile-picture__image, "
        "img.profile-photo-edit__preview, "
        "img.top-card__profile-image"
    ):
        src = image.get("src") or image.get("data-delayed-url")
        if src and _is_profile_photo_candidate(image, src, profile_name):
            images.append(
                ProfileImage(
                    url=src,
                    width=_int_or_none(image.get("width")),
                    height=_int_or_none(image.get("height")),
                    source="dom",
                )
            )

    current_markup_candidates: list[Tag] = []
    for image in soup.select(
        "img[src*='profile-displayphoto'], "
        "img[data-delayed-url*='profile-displayphoto']"
    ):
        src = image.get("src") or image.get("data-delayed-url")
        if src and _is_profile_photo_candidate(image, src, profile_name):
            current_markup_candidates.append(image)

    preferred_candidates = [
        image
        for image in current_markup_candidates
        if _ancestor_aria_label_matches(image, "profile photo")
    ]
    if not preferred_candidates:
        preferred_candidates = [
            image
            for image in current_markup_candidates
            if _image_alt_matches_profile(image, profile_name)
        ]
    if not preferred_candidates and current_markup_candidates:
        preferred_candidates = [current_markup_candidates[0]]

    for image in preferred_candidates:
        src = image.get("src") or image.get("data-delayed-url")
        if src:
            images.append(
                ProfileImage(
                    url=src,
                    width=_int_or_none(image.get("width")),
                    height=_int_or_none(image.get("height")),
                    source="dom",
                )
            )
    deduped: list[ProfileImage] = []
    seen: set[str] = set()
    for image in images:
        if image.url not in seen:
            deduped.append(image)
            seen.add(image.url)
    return deduped


def _ancestor_aria_label_matches(image: Tag, label: str) -> bool:
    current = image.parent
    while isinstance(current, Tag):
        if clean_text(current.get("aria-label") or "").lower() == label:
            return True
        current = current.parent
    return False


def _image_alt_matches_profile(image: Tag, profile_name: str | None) -> bool:
    if not profile_name:
        return False
    alt = clean_text(image.get("alt") or "").lower()
    return bool(alt and profile_name.lower() in alt and "profile" in alt)


def _is_profile_photo_candidate(
    image: Tag, url: str, profile_name: str | None = None
) -> bool:
    lowered_url = url.lower()
    if "profile-displaybackground" in lowered_url or "company-logo" in lowered_url:
        return False

    known_profile_selector = any(
        class_name in (image.get("class") or [])
        for class_name in (
            "pv-top-card-profile-picture__image",
            "profile-photo-edit__preview",
            "top-card__profile-image",
        )
    )
    if known_profile_selector:
        return True

    if "profile-displayphoto" not in lowered_url:
        return False

    alt = clean_text(image.get("alt") or "")
    if not alt:
        return True
    if alt.lower().startswith("view company:"):
        return False
    return _image_alt_matches_profile(image, profile_name)


def _image_urls(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        url = value.get("url") or value.get("@id")
        if isinstance(url, str):
            yield url
    elif isinstance(value, list):
        for item in value:
            yield from _image_urls(item)


def _find_jsonld_person(soup: BeautifulSoup) -> dict[str, Any]:
    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        text = script.string or script.get_text()
        if not text:
            continue
        for obj in _json_objects(text):
            type_value = obj.get("@type")
            types = type_value if isinstance(type_value, list) else [type_value]
            if any(str(item).lower() == "person" for item in types):
                return obj
    return {}


def _json_objects(text: str) -> Iterable[dict[str, Any]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return
    stack = payload if isinstance(payload, list) else [payload]
    while stack:
        item = stack.pop(0)
        if isinstance(item, dict):
            yield item
            graph = item.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)


def _meta_tags(soup: BeautifulSoup) -> dict[str, str]:
    tags: dict[str, str] = {}
    if soup.title and soup.title.string:
        tags["title"] = clean_text(soup.title.string)
    for tag in soup.find_all("meta"):
        key = tag.get("property") or tag.get("name")
        content = tag.get("content")
        if key and content:
            tags[key.lower()] = clean_text(content)
    return tags


def _parse_title(title: str | None) -> tuple[str | None, str | None]:
    if not title:
        return None, None
    clean = re.sub(r"\s*\|\s*LinkedIn\s*$", "", title, flags=re.IGNORECASE).strip()
    if not clean or clean.lower() == "linkedin":
        return None, None
    parts = [part.strip() for part in clean.split(" - ") if part.strip()]
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " - ".join(parts[1:]) or None


def _selector_text(soup: BeautifulSoup, selector: str) -> str | None:
    item = soup.select_one(selector)
    if item:
        text = clean_text(item.get_text(" "))
        return text or None
    return None


def _best_location_line(soup: BeautifulSoup) -> str | None:
    candidates: list[str] = []
    for item in soup.select("main span, main div"):
        text = clean_text(item.get_text(" "))
        if _looks_like_location(text):
            candidates.append(text)
    return min(candidates, key=len) if candidates else None


def _profile_location_from_body_lines(soup: BeautifulSoup, name: str | None) -> str | None:
    if not name:
        return None
    lines = _plain_lines(soup.get_text("\n"))
    try:
        name_index = next(index for index, line in enumerate(lines) if line == name)
    except StopIteration:
        return None
    contact_index = None
    for index in range(name_index + 1, min(len(lines), name_index + 25)):
        if lines[index].lower() == "contact info":
            contact_index = index
            break
    if contact_index is None or contact_index <= name_index + 1:
        return None

    noise = {
        ".",
        "\u00b7",
        "add section",
        "enhance profile",
        "open to",
        "resources",
        "verify in 2 minutes",
    }
    candidates = [
        line
        for line in lines[name_index + 1 : contact_index]
        if line.lower() not in noise and not set(line) <= {"*"}
    ]
    return candidates[-1] if candidates else None


def _address_from_json(value: Any) -> str | None:
    if isinstance(value, str):
        return clean_text(value) or None
    if not isinstance(value, dict):
        return None
    parts = [
        value.get("addressLocality"),
        value.get("addressRegion"),
        value.get("addressCountry"),
    ]
    text = ", ".join(clean_text(str(part)) for part in parts if part)
    return text or None


def _string_from_json(value: Any) -> str | None:
    if isinstance(value, str):
        return clean_text(value) or None
    return None


def _first_present(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _first_index(lines: list[str], predicate: Any) -> int | None:
    for index, line in enumerate(lines):
        if predicate(line):
            return index
    return None


def _line_at(lines: list[str], index: int | None) -> str | None:
    if index is None or index < 0 or index >= len(lines):
        return None
    return lines[index]


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
