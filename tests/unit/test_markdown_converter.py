import pytest
from datetime import datetime

from services.converters import MarkdownConverter, _linkify
from models import (
    JobPosting,
    JobPostingRecord,
    CurriculumVitae,
    CurriculumVitaeRecord,
    Contact,
    CvTransformationPlan,
    CvOptimizationRecord,
)

TEMPLATES_DIR = "templates/markdown"


@pytest.fixture
def converter():
    return MarkdownConverter(templates_dir=TEMPLATES_DIR)


class TestLinkify:
    def test_linkifies_https_url(self):
        result = _linkify("Visit https://example.com for more")
        assert result == "Visit [https://example.com](https://example.com) for more"

    def test_linkifies_http_url(self):
        result = _linkify("See http://example.com")
        assert result == "See [http://example.com](http://example.com)"

    def test_truncates_long_url_display(self):
        long_url = "https://example.com/very/long/path/that/exceeds/sixty/characters/total"
        result = _linkify(long_url)
        assert "[https://example.com/very/long/path/that/exceeds/sixty/cha...]" in result
        assert result.endswith(f"]({long_url})")

    def test_preserves_text_without_urls(self):
        text = "No URLs here, just plain text"
        assert _linkify(text) == text

    def test_linkifies_multiple_urls(self):
        text = "See https://one.com and https://two.com"
        result = _linkify(text)
        assert "[https://one.com](https://one.com)" in result
        assert "[https://two.com](https://two.com)" in result


class TestConvertJobPosting:
    @pytest.fixture
    def sample_job_posting(self):
        return JobPosting(
            url="https://example.com/job/123",
            company="Acme Corp",
            title="Software Engineer",
            industry="Technology",
            description="Build great software",
            experience_level="Mid-level",
            responsibilities=["Write code", "Review PRs"],
            technical_skills=["Python", "Testing"],
        )

    @pytest.fixture
    def sample_record(self):
        return JobPostingRecord(
            identifier="acme-software-engineer",
            filepath="job-postings/acme-software-engineer/job-posting.json",
            url="https://example.com/job/123",
            company="Acme Corp",
            title="Software Engineer",
            experience_level="Mid-level",
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        )

    def test_title_includes_company(self, converter, sample_job_posting):
        result = converter.convert_job_posting(sample_job_posting)
        assert "# Software Engineer at Acme Corp" in result

    def test_title_omits_not_specified_company(self, converter):
        job = JobPosting(
            url="https://example.com/job/456",
            company="Not specified",
            title="Developer",
            industry="Tech",
            description="A job",
            experience_level="Senior",
        )
        result = converter.convert_job_posting(job)
        assert "# Developer" in result
        assert "at Not specified" not in result

    def test_includes_responsibilities(self, converter, sample_job_posting):
        result = converter.convert_job_posting(sample_job_posting)
        assert "- Write code" in result
        assert "- Review PRs" in result

    def test_includes_skills(self, converter, sample_job_posting):
        result = converter.convert_job_posting(sample_job_posting)
        assert "- Python" in result
        assert "- Testing" in result

    def test_no_frontmatter_without_record(self, converter, sample_job_posting):
        result = converter.convert_job_posting(sample_job_posting)
        assert not result.startswith("---")

    def test_frontmatter_with_record(self, converter, sample_job_posting, sample_record):
        result = converter.convert_job_posting(sample_job_posting, sample_record)
        assert result.startswith("---\n")
        assert "identifier: acme-software-engineer" in result
        assert "company: Acme Corp" in result

    def test_convert_dispatches_job_posting(self, converter, sample_job_posting):
        result = converter.convert(sample_job_posting)
        assert "# Software Engineer at Acme Corp" in result
        assert not result.startswith("---")


class TestConvertCv:
    @pytest.fixture
    def sample_cv(self):
        return CurriculumVitae(
            name="Jane Doe",
            profession="Software Engineer",
            contact=Contact(
                city="San Francisco",
                state="CA",
                email="jane@example.com",
                phone="555-1234",
                linkedin="linkedin.com/in/janedoe",
                github="github.com/janedoe",
            ),
            core_expertise=["Python", "Testing"],
            summary_of_qualifications="10 years experience",
            education=[],
            experience=[],
            additional_experience=[],
            areas_of_expertise=[],
            languages=[],
        )

    @pytest.fixture
    def sample_record(self):
        return CurriculumVitaeRecord(
            identifier="jane-doe",
            filepath="cvs/jane-doe/cv.json",
            name="Jane Doe",
            profession="Software Engineer",
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        )

    def test_title_is_name(self, converter, sample_cv):
        result = converter.convert_cv(sample_cv)
        assert "# Jane Doe" in result

    def test_includes_profession(self, converter, sample_cv):
        result = converter.convert_cv(sample_cv)
        assert "## Software Engineer" in result

    def test_includes_contact(self, converter, sample_cv):
        result = converter.convert_cv(sample_cv)
        assert "jane@example.com" in result
        assert "San Francisco, CA" in result

    def test_includes_core_expertise(self, converter, sample_cv):
        result = converter.convert_cv(sample_cv)
        assert "Python" in result
        assert "Testing" in result

    def test_no_frontmatter_without_record(self, converter, sample_cv):
        result = converter.convert_cv(sample_cv)
        assert not result.startswith("---")

    def test_frontmatter_with_record(self, converter, sample_cv, sample_record):
        result = converter.convert_cv(sample_cv, sample_record)
        assert result.startswith("---\n")
        assert "identifier: jane-doe" in result
        assert "profession: Software Engineer" in result

    def test_convert_dispatches_cv(self, converter, sample_cv):
        result = converter.convert(sample_cv)
        assert "# Jane Doe" in result
        assert not result.startswith("---")


class TestConvertTransformationPlan:
    @pytest.fixture
    def sample_plan(self):
        return CvTransformationPlan(
            job_title="Staff Engineer",
            company="Globex",
            matching_skills=["Python", "system design"],
            missing_skills=["Rust"],
            profession_update="Staff Software Engineer",
        )

    @pytest.fixture
    def sample_record(self):
        return CvOptimizationRecord(
            identifier="globex-staff-engineer-opt",
            job_posting_identifier="globex-staff-engineer",
            base_cv_identifier="jane-doe",
            transformation_plan_filepath="job-postings/globex-staff-engineer/cvs/globex-staff-engineer-opt/transformation-plan.json",
            job_title="Staff Engineer",
            company="Globex",
            created_at=datetime(2024, 1, 1),
        )

    def test_title_includes_job_and_company(self, converter, sample_plan):
        result = converter.convert_transformation_plan(sample_plan)
        assert "# Transformation Plan: Staff Engineer at Globex" in result

    def test_includes_matching_skills(self, converter, sample_plan):
        result = converter.convert_transformation_plan(sample_plan)
        assert "- Python" in result
        assert "- system design" in result

    def test_includes_missing_skills(self, converter, sample_plan):
        result = converter.convert_transformation_plan(sample_plan)
        assert "- Rust" in result

    def test_no_frontmatter_without_record(self, converter, sample_plan):
        result = converter.convert_transformation_plan(sample_plan)
        assert not result.startswith("---")

    def test_frontmatter_with_record(self, converter, sample_plan, sample_record):
        result = converter.convert_transformation_plan(sample_plan, sample_record)
        assert result.startswith("---\n")
        assert "identifier: globex-staff-engineer-opt" in result
        assert "job_posting_identifier: globex-staff-engineer" in result

    def test_convert_dispatches_plan(self, converter, sample_plan):
        result = converter.convert(sample_plan)
        assert "# Transformation Plan: Staff Engineer at Globex" in result
        assert not result.startswith("---")
