"""
Tests for Pydantic schemas — verify that response models serialize correctly
and handle missing/optional fields gracefully.
"""

from app.schemas import (
    Certification,
    Education,
    ErrorResponse,
    Experience,
    Language,
    ProfileResponse,
)


def test_profile_response_minimal():
    """ProfileResponse should work with only required fields."""
    resp = ProfileResponse(profile_url="https://www.linkedin.com/in/test")
    assert resp.success is True
    assert resp.profile_url == "https://www.linkedin.com/in/test"
    assert resp.first_name is None
    assert resp.experience == []
    assert resp.skills == []
    assert resp.source == "voyager"


def test_profile_response_full():
    """ProfileResponse should correctly store all fields."""
    resp = ProfileResponse(
        profile_url="https://www.linkedin.com/in/test",
        first_name="John",
        last_name="Doe",
        full_name="John Doe",
        headline="Software Engineer",
        location="San Francisco, CA",
        about="I build things.",
        profile_image_url="https://media.licdn.com/photo.jpg",
        experience=[
            Experience(
                title="Senior Engineer",
                company="Google",
                location="Mountain View",
                start_date="Jan 2020",
                end_date="Present",
            )
        ],
        education=[
            Education(
                school="MIT",
                degree="BS",
                field_of_study="Computer Science",
                start_year="2014",
                end_year="2018",
            )
        ],
        skills=["Python", "FastAPI", "Docker"],
        certifications=[
            Certification(
                name="AWS Solutions Architect",
                issuing_organization="Amazon",
            )
        ],
        languages=[Language(name="English", proficiency="Native")],
    )
    assert resp.full_name == "John Doe"
    assert len(resp.experience) == 1
    assert resp.experience[0].company == "Google"
    assert len(resp.skills) == 3
    assert resp.certifications[0].name == "AWS Solutions Architect"


def test_experience_optional_fields():
    """Experience model should allow all fields to be None."""
    exp = Experience()
    assert exp.title is None
    assert exp.company is None
    assert exp.description is None


def test_error_response():
    """ErrorResponse should have success=False by default."""
    err = ErrorResponse(error="Something broke")
    assert err.success is False
    assert err.error == "Something broke"
    assert err.detail is None


def test_profile_response_serialization():
    """Verify JSON serialization produces expected keys."""
    resp = ProfileResponse(profile_url="https://www.linkedin.com/in/test")
    data = resp.model_dump()
    assert "success" in data
    assert "profile_url" in data
    assert "experience" in data
    assert "skills" in data
    assert "source" in data
    assert isinstance(data["experience"], list)
