import json
from pathlib import Path

import pytest

from post_extractor import (
    GenericHtmlExtractor,
    UpworkExtractor,
    WelcomeToTheJungleExtractor,
    extract_job_posting,
    select_extractor,
)
from post_extractor import cli

FIXTURES = Path(__file__).parent.parent / "fixtures" / "post_extractor"


def make_saved_page(
    description: str,
    title: str = "Test Job",
    attachments: list[dict[str, object]] | None = None,
    occupation_pref_label: str | None = None,
    ontology_skill_groups: list[dict[str, object]] | None = None,
    additional_skills: list[str] | None = None,
    category_name: str | None = None,
    category_group_name: str | None = None,
    workload: str | None = None,
    engagement_duration_label: str | None = None,
    engagement_duration_weeks: int | None = None,
    contractor_tier: int | None = None,
    project_types: list[str] | None = None,
    countries: list[str] | None = None,
    timezones: list[str] | None = None,
    screening_questions: list[str] | None = None,
    location_check_required: bool | None = None,
    should_have_portfolio: bool | None = None,
    rising_talent: bool | None = None,
    min_job_success_score: int | None = None,
    min_odesk_hours: int | None = None,
) -> str:
    attachments = attachments or []
    ontology_skill_groups = ontology_skill_groups or []
    additional_skills = additional_skills or []
    project_types = project_types or []
    countries = countries or []
    timezones = timezones or []
    screening_questions = screening_questions or []
    payload: list[object] = [
        ["Reactive", 1],
        {"vuex": 2},
        {"jobDetails": 3},
        {"job": 4, "sands": 9},
        {
            "uid": 5,
            "title": 6,
            "description": 7,
            "attachments": 8,
        },
        "123456",
        title,
        description,
        [],
        {
            "occupation": 10,
            "ontologySkills": 11,
            "additionalSkills": 12,
        },
        [],
        [],
    ]

    attachment_indexes = []
    for attachment in attachments:
        file_name_index = len(payload)
        payload.append(attachment["fileName"])

        uri_index = len(payload)
        payload.append(attachment["uri"])

        attachment_index = len(payload)
        payload.append(
            {
                "fileName": file_name_index,
                "uri": uri_index,
            }
        )
        attachment_indexes.append(attachment_index)

    payload[8] = attachment_indexes

    if occupation_pref_label:
        pref_label_index = len(payload)
        payload.append(occupation_pref_label)

        occupation_index = len(payload)
        payload.append({"prefLabel": pref_label_index})
        payload[9]["occupation"] = occupation_index

    ontology_group_indexes = []
    for group in ontology_skill_groups:
        children_indexes = []
        for child_name in group.get("children", []):
            child_name_index = len(payload)
            payload.append(child_name)

            child_index = len(payload)
            payload.append({"name": child_name_index})
            children_indexes.append(child_index)

        children_list_index = len(payload)
        payload.append(children_indexes)

        group_name_index = len(payload)
        payload.append(group["name"])

        group_index = len(payload)
        payload.append(
            {
                "name": group_name_index,
                "children": children_list_index,
            }
        )
        ontology_group_indexes.append(group_index)

    payload[9]["ontologySkills"] = len(payload)
    payload.append(ontology_group_indexes)

    additional_skill_indexes = []
    for skill_name in additional_skills:
        skill_name_index = len(payload)
        payload.append(skill_name)

        skill_index = len(payload)
        payload.append({"name": skill_name_index})
        additional_skill_indexes.append(skill_index)

    payload[9]["additionalSkills"] = len(payload)
    payload.append(additional_skill_indexes)

    if category_name:
        category_name_index = len(payload)
        payload.append(category_name)

        category_index = len(payload)
        payload.append({"name": category_name_index})
        payload[4]["category"] = category_index

    if category_group_name:
        category_group_name_index = len(payload)
        payload.append(category_group_name)

        category_group_index = len(payload)
        payload.append({"name": category_group_name_index})
        payload[4]["categoryGroup"] = category_group_index

    if workload:
        workload_index = len(payload)
        payload.append(workload)
        payload[4]["workload"] = workload_index

    if engagement_duration_label:
        engagement_duration_label_index = len(payload)
        payload.append(engagement_duration_label)

        engagement_duration_index = len(payload)
        payload.append({"label": engagement_duration_label_index})
        if engagement_duration_weeks is not None:
            weeks_index = len(payload)
            payload.append(engagement_duration_weeks)
            payload[engagement_duration_index]["weeks"] = weeks_index
        payload[4]["engagementDuration"] = engagement_duration_index

    if contractor_tier is not None:
        contractor_tier_index = len(payload)
        payload.append(contractor_tier)
        payload[4]["contractorTier"] = contractor_tier_index

    if project_types:
        project_type_indexes = []
        for project_type in project_types:
            project_type_label_index = len(payload)
            payload.append(project_type)

            project_type_index = len(payload)
            payload.append({"label": project_type_label_index})
            project_type_indexes.append(project_type_index)

        payload[4]["segmentationData"] = len(payload)
        payload.append(project_type_indexes)

    qualification_index = None
    if any(
        value
        for value in (
            countries,
            timezones,
            screening_questions,
        )
    ) or any(
        value is not None
        for value in (
            location_check_required,
            should_have_portfolio,
            rising_talent,
            min_job_success_score,
            min_odesk_hours,
        )
    ):
        qualification_index = len(payload)
        payload.append({})
        payload[4]["qualifications"] = qualification_index

    if countries and qualification_index is not None:
        country_indexes = []
        for country in countries:
            country_index = len(payload)
            payload.append(country)
            country_indexes.append(country_index)
        payload[qualification_index]["countries"] = len(payload)
        payload.append(country_indexes)

    if timezones and qualification_index is not None:
        timezone_indexes = []
        for timezone in timezones:
            timezone_index = len(payload)
            payload.append(timezone)
            timezone_indexes.append(timezone_index)
        payload[qualification_index]["timezones"] = len(payload)
        payload.append(timezone_indexes)

    if location_check_required is not None and qualification_index is not None:
        payload[qualification_index]["locationCheckRequired"] = len(payload)
        payload.append(location_check_required)

    if should_have_portfolio is not None and qualification_index is not None:
        payload[qualification_index]["shouldHavePortfolio"] = len(payload)
        payload.append(should_have_portfolio)

    if rising_talent is not None and qualification_index is not None:
        payload[qualification_index]["risingTalent"] = len(payload)
        payload.append(rising_talent)

    if min_job_success_score is not None and qualification_index is not None:
        payload[qualification_index]["minJobSuccessScore"] = len(payload)
        payload.append(min_job_success_score)

    if min_odesk_hours is not None and qualification_index is not None:
        payload[qualification_index]["minOdeskHours"] = len(payload)
        payload.append(min_odesk_hours)

    if screening_questions:
        question_indexes = []
        for question in screening_questions:
            question_text_index = len(payload)
            payload.append(question)

            question_index = len(payload)
            payload.append({"question": question_text_index})
            question_indexes.append(question_index)

        payload[4]["questions"] = len(payload)
        payload.append(question_indexes)

    raw_json = json.dumps(payload)
    return f'<html><body><script type="application/json">{raw_json}</script></body></html>'


def make_generic_job_page() -> str:
    return """\
<html>
  <head>
    <title>Senior Python Developer | Example Co</title>
  </head>
  <body>
    <nav>Home Jobs Sign in</nav>
    <main>
      <section>
        <h1>Senior Python Developer</h1>
        <p>Join the platform team building backend services for job seekers.</p>
      </section>
      <section>
        <h2>Responsibilities</h2>
        <ul>
          <li>Build APIs</li>
          <li>Improve reliability</li>
        </ul>
      </section>
      <section>
        <h2>Requirements</h2>
        <p>Python, SQL, and clear communication.</p>
        <a href="/files/brief.pdf">Download brief</a>
      </section>
    </main>
    <footer>Privacy Terms</footer>
  </body>
</html>
"""


def make_welcome_to_the_jungle_job_page() -> str:
    job_posting = {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": "Software Engineer",
        "hiringOrganization": {
            "@type": "Organization",
            "name": "Example Co",
        },
        "description": (
            "<h1>Requirements</h1>"
            "<ul>"
            "<li>Strong Python experience</li>,"
            "<li>Clear written communication</li>"
            "</ul>"
        ),
        "responsibilities": (
            "<ul>"
            "<li>Build internal tools</li>,"
            "<li>Work across distributed teams</li>"
            "</ul>"
        ),
        "skills": (
            "<ul>"
            "<li>Python</li>,"
            "<li>APIs</li>"
            "</ul>"
        ),
        "jobBenefits": (
            "<ul>"
            "<li>Remote work</li>,"
            "<li>Home office stipend</li>"
            "</ul>"
        ),
    }
    raw_json = json.dumps(job_posting)
    return f"""\
<html>
  <head>
    <title>Example Co Software Engineer | Welcome to the Jungle</title>
    <meta property="og:site_name" content="Welcome to the Jungle" />
    <script type="application/ld+json">{raw_json}</script>
  </head>
  <body>
    <main><h1>Software Engineer</h1></main>
    <div data-testid="salary-section"><span>$120k</span><span> + Equity</span></div>
    <div data-testid="experience-section">Junior and Mid level</div>
    <div data-testid="job-locations">
      <div>Remote from US</div>
      <div>Remote from Canada</div>
    </div>
    <div data-testid="job-technology-used">
      <div disabled="">Python</div>
      <div disabled="">GraphQL</div>
      <div disabled="">AWS</div>
    </div>
    <div data-testid="company-sector-tags">
      <span>SaaS</span>
      <span>Developer Tools</span>
    </div>
  </body>
</html>
"""


def make_saved_wttj_job_page_without_branding_text() -> str:
    return """\
<html>
  <head>
    <title>Software Engineer</title>
    <script type="application/ld+json">{"@context":"https://schema.org/","@type":"JobPosting","title":"Software Engineer","hiringOrganization":{"@type":"Organization","name":"Example Co"}}</script>
  </head>
  <body>
    <div data-testid="salary-section">$120k + Equity</div>
    <div data-testid="experience-section">Junior and Mid level</div>
    <div data-testid="job-locations"><div>Remote from US</div></div>
    <div data-testid="job-technology-used"><div>Python</div></div>
    <div data-testid="company-sector-tags"><span>SaaS</span></div>
  </body>
</html>
"""


def make_wttj_job_page_with_senior_and_expert_levels() -> str:
    return """\
<html>
  <head>
    <script type="application/ld+json">{"@context":"https://schema.org/","@type":"JobPosting","title":"Software Engineer","hiringOrganization":{"@type":"Organization","name":"Example Co"}}</script>
  </head>
  <body>
    <div data-testid="experience-section">Senior and Expert level</div>
    <div data-testid="job-technology-used"><div>Python</div></div>
    <div data-testid="company-sector-tags"><span>SaaS</span></div>
  </body>
</html>
"""


def test_extracts_title_and_markdown_body():
    html = make_saved_page(
        "<p>Hello <strong>world</strong>.</p><ul><li>One</li><li>Two</li></ul>"
    )

    job = UpworkExtractor.from_string(html).extract()

    assert job.title == "Test Job"
    assert job.to_markdown() == "# Test Job\n\nHello **world**.\n\n- One\n- Two\n"


def test_preserves_plain_text_descriptions():
    html = make_saved_page("First paragraph.\n\nSecond paragraph.")

    job = UpworkExtractor.from_string(html).extract()

    assert job.to_markdown() == "# Test Job\n\nFirst paragraph.\n\nSecond paragraph.\n"


def test_renders_links_and_ordered_lists():
    html = make_saved_page(
        "<p>Read <a href=\"https://example.com\">this brief</a>.</p>"
        "<ol><li>First</li><li>Second</li></ol>"
    )

    job = UpworkExtractor.from_string(html).extract()

    assert "[this brief](https://example.com)" in job.to_markdown()
    assert "1. First" in job.to_markdown()
    assert "2. Second" in job.to_markdown()


def test_renders_attachments_as_markdown_links():
    html = make_saved_page(
        "<p>Converted</p>",
        attachments=[
            {
                "fileName": "brief.pdf",
                "uri": "/att/download/openings/123/attachments/abc/download",
            },
            {
                "fileName": "screenshot.png",
                "uri": "/att/download/openings/123/attachments/def/download",
            },
        ],
    )

    job = UpworkExtractor.from_string(html).extract()

    assert "## Attachments" in job.to_markdown()
    assert "- [brief.pdf](https://www.upwork.com/att/download/openings/123/attachments/abc/download)" in job.to_markdown()
    assert "- [screenshot.png](https://www.upwork.com/att/download/openings/123/attachments/def/download)" in job.to_markdown()


def test_upwork_extracts_structured_skills_and_expertise():
    html = make_saved_page(
        "<p>Converted</p>",
        occupation_pref_label="Machine Learning",
        ontology_skill_groups=[
            {
                "name": "Machine Learning Methods",
                "children": ["Natural Language Processing"],
            },
            {
                "name": "Machine Learning Languages",
                "children": ["Python"],
            },
        ],
        additional_skills=[
            "OpenAI API",
            "API Integration",
            "Vector Database",
            "Pinecone",
            "Python",
        ],
    )

    job = UpworkExtractor.from_string(html).extract()

    assert job.skills_and_expertise == [
        "Machine Learning",
        "Natural Language Processing",
        "Python",
        "OpenAI API",
        "API Integration",
        "Vector Database",
        "Pinecone",
    ]
    assert "## Skills and Expertise" in job.to_markdown()
    assert "- Machine Learning" in job.to_markdown()
    assert "- Natural Language Processing" in job.to_markdown()
    assert "- API Integration" in job.to_markdown()
    assert job.to_markdown().count("- Python") == 1


def test_upwork_example_file_contains_skills_and_expertise_in_output():
    html = (FIXTURES / "upwork.html").read_text(encoding="utf-8")

    job = UpworkExtractor.from_string(html).extract()

    assert "Natural Language Processing" in job.skills_and_expertise
    assert "Python" in job.skills_and_expertise
    assert "OpenAI API" in job.skills_and_expertise
    assert "Vector Database" in job.skills_and_expertise
    assert "Pinecone" in job.skills_and_expertise
    assert "## Skills and Expertise" in job.to_markdown()


def test_upwork_extracts_additional_payload_fields():
    html = make_saved_page(
        "<p>Converted</p>",
        category_name="AI & Machine Learning",
        category_group_name="Data Science & Analytics",
        workload="Less than 30 hrs/week",
        engagement_duration_label="Less than 1 month",
        engagement_duration_weeks=3,
        contractor_tier=3,
        project_types=["One-time project"],
        countries=["United States"],
        timezones=["UTC-05:00"],
        screening_questions=[
            "Describe a similar retrieval workflow you have built.",
        ],
        location_check_required=True,
        should_have_portfolio=False,
        rising_talent=False,
        min_job_success_score=90,
        min_odesk_hours=100,
    )

    job = UpworkExtractor.from_string(html).extract()

    assert job.category == "AI & Machine Learning"
    assert job.category_group == "Data Science & Analytics"
    assert job.workload == "Less than 30 hrs/week"
    assert job.engagement_duration == "Less than 1 month (3 weeks)"
    assert job.contractor_tier == "3"
    assert job.project_types == ["One-time project"]
    assert job.countries == ["United States"]
    assert job.timezones == ["UTC-05:00"]
    assert job.screening_questions == [
        "Describe a similar retrieval workflow you have built.",
    ]
    assert job.location_requirement == "Required"
    assert job.portfolio_requirement == "Not required"
    assert job.rising_talent_preference == "Not required"
    assert job.job_success_score == "90%"
    assert job.odesk_hours == "100 hours"
    assert "- **Category:** AI & Machine Learning" in job.to_markdown()
    assert "- **Project Types:** One-time project" in job.to_markdown()
    assert "- **Timezones:** UTC-05:00" in job.to_markdown()
    assert "## Screening Questions" in job.to_markdown()


def test_upwork_example_file_contains_additional_payload_fields():
    html = (FIXTURES / "upwork.html").read_text(encoding="utf-8")

    job = UpworkExtractor.from_string(html).extract()

    assert job.category == "AI & Machine Learning"
    assert job.category_group == "Data Science & Analytics"
    assert job.workload == "Less than 30 hrs/week"
    assert job.engagement_duration == "Less than 1 month (3 weeks)"
    assert job.contractor_tier == "3"
    assert job.project_types == ["One-time project"]
    assert job.countries == ["United States"]
    assert job.timezones == ["UTC-05:00"]
    assert job.location_requirement == "Required"
    assert job.portfolio_requirement == "Not required"
    assert job.rising_talent_preference == "Not required"
    assert job.job_success_score == "0%"
    assert job.odesk_hours == "0 hours"
    assert "- **Category Group:** Data Science & Analytics" in job.to_markdown()
    assert "- **Engagement Duration:** Less than 1 month (3 weeks)" in job.to_markdown()


def test_upwork_latest_nuxt_html_is_detected_and_extracted():
    html = (FIXTURES / "upwork-latest.html").read_text(encoding="utf-8")

    assert UpworkExtractor.matches(html) is True
    assert select_extractor(html) is UpworkExtractor

    job = UpworkExtractor.from_string(html).extract()

    assert job.title == "PHP 5 to 8 Migration and Rebuild"
    assert "PHP 5 platform to PHP 8" in job.to_markdown()
    assert job.category == "Full Stack Development"
    assert job.workload == "More than 30 hrs/week"
    assert job.engagement_duration == "1 to 3 months"
    assert job.experience.startswith("Expert")
    assert job.project_types == ["Complex project"]
    assert job.countries == ["Worldwide"]
    assert job.job_success_score == "90%"
    assert job.rising_talent_preference == "Preferred"
    assert len(job.screening_questions or []) == 5
    assert "PHP" in (job.skills_and_expertise or [])
    assert "MySQL" in (job.skills_and_expertise or [])


def test_extract_job_posting_falls_back_to_generic_html():
    job = extract_job_posting(
        make_generic_job_page(),
        source_url="https://example.com/jobs/senior-python-developer",
    )

    assert job.title == "Senior Python Developer"
    assert "Responsibilities" in job.to_markdown()
    assert "[Download brief](https://example.com/files/brief.pdf)" in job.to_markdown()
    assert "Home Jobs Sign in" not in job.to_markdown()
    assert "Privacy Terms" not in job.to_markdown()


def test_select_extractor_returns_upwork_for_upwork_payload():
    extractor = select_extractor(make_saved_page("<p>Converted</p>"))

    assert extractor is UpworkExtractor


def test_select_extractor_returns_generic_for_generic_page():
    extractor = select_extractor(
        make_generic_job_page(),
        source_url="https://example.com/jobs/senior-python-developer",
    )

    assert extractor is GenericHtmlExtractor


def test_select_extractor_returns_wttj_for_wttj_payload():
    extractor = select_extractor(
        make_welcome_to_the_jungle_job_page(),
        source_url="https://app.welcometothejungle.com/jobs/example",
    )

    assert extractor is WelcomeToTheJungleExtractor


def test_select_extractor_returns_wttj_for_saved_wttj_html_without_branding_text():
    extractor = select_extractor(make_saved_wttj_job_page_without_branding_text())

    assert extractor is WelcomeToTheJungleExtractor


def test_upwork_matches_checks_content_signature():
    assert UpworkExtractor.matches(make_saved_page("<p>Converted</p>")) is True
    assert UpworkExtractor.matches(make_generic_job_page()) is False


def test_generic_matches_checks_content_signature():
    assert GenericHtmlExtractor.matches(make_generic_job_page()) is True
    assert GenericHtmlExtractor.matches("<html><body><p>Too short</p></body></html>") is False


def test_wttj_matches_checks_content_signature():
    assert WelcomeToTheJungleExtractor.matches(
        make_welcome_to_the_jungle_job_page(),
        source_url="https://app.welcometothejungle.com/jobs/example",
    ) is True
    assert WelcomeToTheJungleExtractor.matches(
        make_saved_wttj_job_page_without_branding_text()
    ) is True
    assert WelcomeToTheJungleExtractor.matches(make_generic_job_page()) is False


def test_wttj_extractor_extracts_company_and_structured_sections():
    job = WelcomeToTheJungleExtractor.from_string(
        make_welcome_to_the_jungle_job_page(),
        source_url="https://app.welcometothejungle.com/jobs/example",
    ).extract()

    assert job.title == "Software Engineer"
    assert job.company == "Example Co"
    assert job.salary == "$120k + Equity"
    assert job.experience == "Junior, Mid"
    assert job.locations == ["Remote from US", "Remote from Canada"]
    assert job.technologies == ["Python", "GraphQL", "AWS"]
    assert job.company_sector_tags == ["SaaS", "Developer Tools"]
    assert job.data_testid_values is not None
    assert job.data_testid_values["salary-section"] == ["$120k + Equity"]
    assert "job-technology-used" in job.data_testid_values
    assert "company-sector-tags" in job.data_testid_values
    assert "Build internal tools" in job.to_markdown()
    assert "Home office stipend" in job.to_markdown()
    assert "- **Company:** Example Co" in job.to_markdown()
    assert "- **Salary:** $120k + Equity" in job.to_markdown()
    assert "- **Experience:** Junior, Mid" in job.to_markdown()
    assert "- **Locations:** Remote from US, Remote from Canada" in job.to_markdown()
    assert "- **Technologies:** Python, GraphQL, AWS" in job.to_markdown()
    assert "- **Sectors:** SaaS, Developer Tools" in job.to_markdown()


def test_extract_job_posting_prefers_wttj_extractor_when_available():
    job = extract_job_posting(
        make_welcome_to_the_jungle_job_page(),
        source_url="https://app.welcometothejungle.com/jobs/example",
    )

    assert job.company == "Example Co"
    assert job.salary == "$120k + Equity"
    assert "# Skills" in job.to_markdown()
    assert job.technologies == ["Python", "GraphQL", "AWS"]


def test_wttj_experience_includes_expert_level():
    job = extract_job_posting(make_wttj_job_page_with_senior_and_expert_levels())

    assert job.experience == "Senior, Expert"
    assert "- **Experience:** Senior, Expert" in job.to_markdown()


def test_generic_html_extractor_uses_title_when_h1_is_missing():
    html = """\
<html>
  <head><title>Staff Data Engineer</title></head>
  <body>
    <article>
      <p>This role owns the analytics platform and event pipelines for internal teams.</p>
      <h2>Qualifications</h2>
      <p>Python, SQL, and warehouse design experience.</p>
    </article>
  </body>
</html>
"""

    job = GenericHtmlExtractor.from_string(html).extract()

    assert job.title == "Staff Data Engineer"
    assert "analytics platform" in job.to_markdown()


def test_cli_writes_markdown_file(capsys, tmp_path: Path):
    saved_page = tmp_path / "posting.html"
    saved_page.write_text(make_saved_page("<p>Converted</p>"), encoding="utf-8")

    exit_code = cli.main([str(saved_page)])
    captured = capsys.readouterr()
    output_file = tmp_path / "posting.md"

    assert exit_code == 0
    assert output_file.read_text(encoding="utf-8") == "# Test Job\n\nConverted\n"
    assert output_file.exists()
    assert captured.out == "Using UpworkExtractor...\n"
    assert captured.err == ""


def test_cli_writes_markdown_to_stdout_when_piped(monkeypatch, capsys, tmp_path: Path):
    saved_page = tmp_path / "posting.html"
    saved_page.write_text(make_saved_page("<p>Converted</p>"), encoding="utf-8")
    monkeypatch.setattr(cli, "_stdout_is_pipe", lambda: True)

    exit_code = cli.main([str(saved_page)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "# Test Job\n\nConverted\n"
    assert captured.err == "Using UpworkExtractor...\n"
    assert not (tmp_path / "posting.md").exists()


def test_cli_writes_markdown_file_to_explicit_output_path(capsys, tmp_path: Path):
    saved_page = tmp_path / "posting.html"
    output_file = tmp_path / "custom-output.md"
    saved_page.write_text(make_saved_page("<p>Converted</p>"), encoding="utf-8")

    exit_code = cli.main([str(saved_page), str(output_file)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_file.exists()
    assert output_file.read_text(encoding="utf-8") == "# Test Job\n\nConverted\n"
    assert captured.out == "Using UpworkExtractor...\n"
    assert captured.err == ""
    assert not (tmp_path / "posting.md").exists()


def test_cli_writes_markdown_file_for_url(monkeypatch, capsys, tmp_path: Path):
    html = make_saved_page("<p>Converted</p>", title="Remote Role")

    class MockHeaders:
        @staticmethod
        def get_content_charset() -> str:
            return "utf-8"

    class MockResponse:
        headers = MockHeaders()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return html.encode("utf-8")

    def mock_urlopen(url: str) -> MockResponse:
        assert url == "https://example.com/jobs/senior-python-developer"
        return MockResponse()

    monkeypatch.setattr(cli, "urlopen", mock_urlopen)
    monkeypatch.chdir(tmp_path)

    exit_code = cli.main(["https://example.com/jobs/senior-python-developer"])
    captured = capsys.readouterr()
    output_file = tmp_path / "senior-python-developer.md"

    assert exit_code == 0
    assert output_file.exists()
    assert output_file.read_text(encoding="utf-8") == "# Remote Role\n\nConverted\n"
    assert captured.out == "Using UpworkExtractor...\n"
    assert captured.err == ""


def test_cli_writes_url_markdown_file_to_explicit_output_path(monkeypatch, capsys, tmp_path: Path):
    html = make_generic_job_page()

    class MockHeaders:
        @staticmethod
        def get_content_charset() -> str:
            return "utf-8"

    class MockResponse:
        headers = MockHeaders()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return html.encode("utf-8")

    output_file = tmp_path / "named-output.md"
    monkeypatch.setattr(cli, "urlopen", lambda _: MockResponse())
    monkeypatch.chdir(tmp_path)

    exit_code = cli.main(["https://example.com/jobs/senior-python-developer", str(output_file)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_file.exists()
    assert "Senior Python Developer" in output_file.read_text(encoding="utf-8")
    assert captured.out == "Using GenericHtmlExtractor...\n"
    assert captured.err == ""
    assert not (tmp_path / "senior-python-developer.md").exists()


def test_cli_writes_index_markdown_file_for_trailing_slash_url(monkeypatch, tmp_path: Path):
    html = make_saved_page("<p>Converted</p>")

    class MockHeaders:
        @staticmethod
        def get_content_charset() -> str:
            return "utf-8"

    class MockResponse:
        headers = MockHeaders()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return html.encode("utf-8")

    monkeypatch.setattr(cli, "urlopen", lambda _: MockResponse())
    monkeypatch.chdir(tmp_path)

    exit_code = cli.main(["https://example.com/jobs/"])

    assert exit_code == 0
    assert (tmp_path / "jobs.md").exists()


def test_cli_writes_markdown_file_for_generic_url(monkeypatch, capsys, tmp_path: Path):
    html = make_generic_job_page()

    class MockHeaders:
        @staticmethod
        def get_content_charset() -> str:
            return "utf-8"

    class MockResponse:
        headers = MockHeaders()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return html.encode("utf-8")

    monkeypatch.setattr(cli, "urlopen", lambda _: MockResponse())
    monkeypatch.chdir(tmp_path)

    exit_code = cli.main(["https://example.com/jobs/senior-python-developer"])
    captured = capsys.readouterr()
    output_file = tmp_path / "senior-python-developer.md"

    assert exit_code == 0
    assert output_file.exists()
    assert "Senior Python Developer" in output_file.read_text(encoding="utf-8")
    assert captured.out == "Using GenericHtmlExtractor...\n"
    assert captured.err == ""


def test_cli_reports_url_fetch_errors(monkeypatch, capsys, tmp_path: Path):
    monkeypatch.setattr(cli, "urlopen", lambda _: (_ for _ in ()).throw(OSError("HTTP Error 403: Forbidden")))
    monkeypatch.chdir(tmp_path)

    exit_code = cli.main(["https://www.upwork.com/jobs/example"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == "Error: HTTP Error 403: Forbidden\n"


def test_wrong_file_error():
    with pytest.raises(ValueError, match="expected Upwork job data"):
        UpworkExtractor.from_string("<html><body>no payload here</body></html>").extract()


def test_cli_fails_when_input_does_not_contain_html(capsys, tmp_path: Path):
    saved_page = tmp_path / "posting.txt"
    saved_page.write_text("plain text only", encoding="utf-8")

    exit_code = cli.main([str(saved_page)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == "Error: Input file does not contain HTML.\n"
    assert not (tmp_path / "posting.md").exists()


def test_cli_fails_when_html_has_no_recognizable_job_content(capsys, tmp_path: Path):
    saved_page = tmp_path / "posting.html"
    saved_page.write_text("<html><body><main><p>Too short</p></main></body></html>", encoding="utf-8")

    exit_code = cli.main([str(saved_page)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == "Error: Could not find recognizable job posting content in this HTML file.\n"
