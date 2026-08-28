from app.errors import InvalidLinkedInUrl
from app.scraper.parsers import (
    normalize_linkedin_profile_url,
    parse_compact_profile_education,
    parse_detail_section_html,
    parse_detail_section_text,
    parse_profile_html,
)


def test_normalize_linkedin_profile_url_accepts_profile_url() -> None:
    url, public_id = normalize_linkedin_profile_url(
        "linkedin.com/in/jane-doe-123/?trk=public_profile"
    )

    assert url == "https://www.linkedin.com/in/jane-doe-123/"
    assert public_id == "jane-doe-123"


def test_normalize_linkedin_profile_url_rejects_non_profile_url() -> None:
    try:
        normalize_linkedin_profile_url("https://example.com/in/jane")
    except InvalidLinkedInUrl as exc:
        assert "linkedin.com" in str(exc)
    else:
        raise AssertionError("Expected InvalidLinkedInUrl")


def test_parse_profile_html_reads_jsonld_and_open_graph() -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="Jane Doe - Staff Engineer | LinkedIn" />
        <meta property="og:image" content="https://example.test/jane.jpg" />
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Person",
          "name": "Jane Doe",
          "jobTitle": "Staff Engineer",
          "address": {
            "@type": "PostalAddress",
            "addressLocality": "Bengaluru",
            "addressCountry": "India"
          }
        }
        </script>
      </head>
      <body><main><h1>Jane Doe</h1></main></body>
    </html>
    """

    profile = parse_profile_html(html, "https://www.linkedin.com/in/jane-doe/")

    assert profile.name == "Jane Doe"
    assert profile.headline == "Staff Engineer"
    assert profile.location == "Bengaluru, India"
    assert profile.profile_images[0].url == "https://example.test/jane.jpg"


def test_parse_profile_html_uses_own_profile_location_before_open_to_work() -> None:
    html = """
    <main>
      <h1>Chirag Kakwani</h1>
      <div>Chirag Kakwani</div>
      <div>.</div>
      <div>Resources</div>
      <div>Enhance profile</div>
      <div>Add section</div>
      <div>Open to</div>
      <div>Verify in 2 minutes</div>
      <div>Greater Delhi Area</div>
      <div>Contact info</div>
      <div>Walmart Global Tech India</div>
      <div>Surat | On-site \u00b7 Hybrid</div>
    </main>
    """

    profile = parse_profile_html(
        html, "https://www.linkedin.com/in/chirag-kakwani-8b4055284/"
    )

    assert profile.location == "Greater Delhi Area"


def test_parse_experience_detail_section() -> None:
    html = """
    <main>
      <ul>
        <li class="pvs-list__paged-list-item">
          <span>Senior Backend Engineer</span>
          <span>Acme Inc \u00b7 Full-time</span>
          <span>Jan 2022 - Present \u00b7 2 yrs</span>
          <span>Remote</span>
          <span>Built search APIs and data pipelines.</span>
        </li>
      </ul>
    </main>
    """

    items = parse_detail_section_html(html, "experience")

    assert items[0].title == "Senior Backend Engineer"
    assert items[0].company == "Acme Inc"
    assert items[0].employment_type == "Full-time"
    assert items[0].end_date == "Present"
    assert items[0].location == "Remote"


def test_detail_section_ignores_unrelated_linkedin_lists() -> None:
    html = """
    <main>
      <ul>
        <li>Career</li>
        <li>Productivity</li>
        <li>Business Analysis and Strategy<span>4,270+ courses</span></li>
        <li>Let the right people know you are open to work</li>
      </ul>
    </main>
    """

    assert parse_detail_section_html(html, "experience") == []


def test_empty_sections_ignore_ad_preference_modal_text() -> None:
    html = """
    <main>
      <h1>Skills</h1>
      <p>When you add new skills they'll show up here</p>
      <li class="artdeco-list__item">Ad Options</li>
      <li class="artdeco-list__item">Why am I seeing this ad?</li>
      <li class="artdeco-list__item">Hide or report this ad</li>
    </main>
    """

    assert parse_detail_section_html(html, "skills") == []
    assert parse_detail_section_html(html.replace("Skills", "Languages"), "languages") == []
    assert parse_detail_section_html(
        html.replace("Skills", "Licenses & certifications").replace(
            "When you add new skills they'll show up here",
            "Nothing to see for now",
        ),
        "certifications",
    ) == []


def test_skill_parser_ignores_recommendation_and_category_noise() -> None:
    text = """
    Skills
    All
    Industry Knowledge
    Tools & Technologies
    More profiles for you
    Meet Shah
    Follow
    Profile language
    English
    """

    assert parse_detail_section_text(text, "skills") == []


def test_experience_parser_trims_more_profiles_block() -> None:
    html = """
    <main>
      <ul>
        <li class="pvs-list__paged-list-item">
          <span>Open Source Developer</span>
          <span>The Terasology Foundation \u00b7 Freelance</span>
          <span>May 2020 - Jun 2021 \u00b7 1 yr 2 mos</span>
          <span>More profiles for you</span>
          <span>Padam Kataria</span>
        </li>
      </ul>
    </main>
    """

    items = parse_detail_section_html(html, "experience")

    assert len(items) == 1
    assert items[0].title == "Open Source Developer"
    assert items[0].description == []


def test_experience_parser_does_not_treat_money_as_date() -> None:
    text = """
    Experience
    - Did in-depth user research with 20+ teens in US
    - Created wireframes
    - Led conversations that led to savings of $10000
    Education
    """

    assert parse_detail_section_text(text, "experience") == []


def test_experience_parser_skips_stray_leading_bullet_before_role() -> None:
    text = """
    Experience
    - Led conversations with growth hackers in US and saved $10000
    Sprinklr
    2021 - 2021
    Customer experience management domain
    Education
    """

    items = parse_detail_section_text(text, "experience")

    assert len(items) == 1
    assert items[0].title == "Sprinklr"
    assert items[0].start_date == "2021"


def test_parse_experience_from_rendered_detail_text() -> None:
    text = """
    Home
    My Network
    Chirag Kakwani
    .
    Experience
    Software Engineer
    Walmart Global Tech India \u00b7 Full-time
    May 2024 - Jul 2026 \u00b7 2 yrs 3 mos
    Bengaluru, Karnataka, India
    Enhance with AI
    technical content intern
    HackerEarth
    Jun 2023 - May 2024 \u00b7 1 yr
    Profile language
    English
    """

    items = parse_detail_section_text(text, "experience")

    assert len(items) == 2
    assert items[0].title == "Software Engineer"
    assert items[0].company == "Walmart Global Tech India"
    assert items[0].employment_type == "Full-time"
    assert items[0].start_date == "May 2024"
    assert items[0].end_date == "Jul 2026"
    assert items[0].location == "Bengaluru, Karnataka, India"
    assert items[1].title == "technical content intern"
    assert items[1].company == "HackerEarth"


def test_parse_education_from_rendered_detail_text() -> None:
    text = """
    Chirag Kakwani
    .
    Education
    Gujarat Technological University (GTU)
    Bachelor of Engineering, Business/Commerce, General
    2019 \u2013 2023
    Profile language
    English
    """

    items = parse_detail_section_text(text, "education")

    assert len(items) == 1
    assert items[0].school == "Gujarat Technological University (GTU)"
    assert items[0].degree == "Bachelor of Engineering"
    assert items[0].field_of_study == "Business/Commerce, General"
    assert items[0].start_date == "2019"
    assert items[0].end_date == "2023"


def test_parse_compact_profile_education_uses_top_card_school() -> None:
    html = """
    <main>
      <p>Share Profile</p>
      <h1>Chirag Kakwani</h1>
      <p>Premium member</p>
      <p>.</p>
      <p>Gujarat Technological University (GTU)</p>
      <p>Walmart Global Tech India</p>
      <p>Greater Delhi Area</p>
      <h2>Experience</h2>
      <p>Add experience</p>
      <p>May 2024</p>
      <p>-</p>
      <p>Jul 2026</p>
      <p>Education</p>
      <p>Add education</p>
      <p>Bachelor of Engineering</p>
      <p>Business/Commerce, General</p>
      <p>2019</p>
      <p>2023</p>
      <p>Have more education?</p>
      <p>Volunteer Experience</p>
    </main>
    """

    items = parse_compact_profile_education(
        html,
        name="Chirag Kakwani",
        location="Greater Delhi Area",
        companies=["Walmart Global Tech India"],
    )

    assert len(items) == 1
    assert items[0].school == "Gujarat Technological University (GTU)"
    assert items[0].degree == "Bachelor of Engineering"
    assert items[0].field_of_study == "Business/Commerce, General"
    assert items[0].start_date == "2019"
    assert items[0].end_date == "2023"


def test_parse_compact_profile_education_prefers_section_school() -> None:
    html = """
    <main>
      <h1>Meet Shah</h1>
      <p>Joined 2020</p>
      <p>Tross (Previously Ayden)</p>
      <p>San Francisco, California, United States</p>
      <h2>Education</h2>
      <p>Add education</p>
      <p>Indian Institute of Technology, Roorkee</p>
      <p>Bachelor of Technology - BTech</p>
      <p>Computer Science</p>
      <p>2019</p>
      <p>2023</p>
      <p>Volunteer Experience</p>
    </main>
    """

    items = parse_compact_profile_education(
        html,
        name="Meet Shah",
        location="San Francisco, California, United States",
        companies=["Tross (Previously Ayden)"],
    )

    assert len(items) == 1
    assert items[0].school == "Indian Institute of Technology, Roorkee"
    assert items[0].degree == "Bachelor of Technology - BTech"
    assert items[0].field_of_study == "Computer Science"
