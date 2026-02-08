import pytest
from pydantic import BaseModel

from services.converters import (
    MarkdownConverter,
    _render,
    _key_to_heading,
    _linkify_urls,
)
from models import JobPosting, CurriculumVitae, Contact


class TestKeyToHeading:
    def test_converts_snake_case(self):
        assert _key_to_heading("technical_skills") == "Technical Skills"

    def test_converts_single_word(self):
        assert _key_to_heading("title") == "Title"

    def test_converts_multiple_underscores(self):
        assert (
            _key_to_heading("summary_of_qualifications") == "Summary Of Qualifications"
        )


class TestLinkifyUrls:
    def test_linkifies_https_url(self):
        result = _linkify_urls("Visit https://example.com for more")
        assert result == "Visit [https://example.com](https://example.com) for more"

    def test_linkifies_http_url(self):
        result = _linkify_urls("See http://example.com")
        assert result == "See [http://example.com](http://example.com)"

    def test_truncates_long_url_display(self):
        long_url = (
            "https://example.com/very/long/path/that/exceeds/sixty/characters/total"
        )
        result = _linkify_urls(long_url)
        assert (
            "[https://example.com/very/long/path/that/exceeds/sixty/cha...]" in result
        )
        assert result.endswith(f"]({long_url})")

    def test_preserves_text_without_urls(self):
        text = "No URLs here, just plain text"
        assert _linkify_urls(text) == text

    def test_linkifies_multiple_urls(self):
        text = "See https://one.com and https://two.com"
        result = _linkify_urls(text)
        assert "[https://one.com](https://one.com)" in result
        assert "[https://two.com](https://two.com)" in result


class TestRender:
    def test_simple_string_values(self):
        data = {"title": "Engineer", "company": "Acme"}
        result = _render(data)
        assert "**Title:** Engineer" in result
        assert "**Company:** Acme" in result

    def test_with_title(self):
        data = {"_title": "My Document", "name": "Test"}
        result = _render(data)
        assert result.startswith("# My Document\n")

    def test_with_custom_level(self):
        data = {"_title": "Subsection", "name": "Test"}
        result = _render(data, level=2)
        assert result.startswith("## Subsection\n")

    def test_list_of_strings_as_bullets(self):
        data = {"skills": ["Python", "Go", "Rust"]}
        result = _render(data)
        assert "**Skills:**" in result
        assert "- Python" in result
        assert "- Go" in result
        assert "- Rust" in result

    def test_nested_dict_as_subsection(self):
        data = {"contact": {"email": "test@example.com", "phone": "555-1234"}}
        result = _render(data)
        assert "# Contact" in result
        assert "**Email:** test@example.com" in result
        assert "**Phone:** 555-1234" in result

    def test_nested_dict_with_title_uses_higher_level(self):
        data = {"_title": "Person", "contact": {"email": "test@example.com"}}
        result = _render(data)
        assert "# Person" in result
        assert "## Contact" in result

    def test_list_of_dicts_with_title_extraction(self):
        data = {
            "experience": [
                {"title": "Engineer", "company": "Acme"},
                {"title": "Developer", "company": "Beta"},
            ]
        }
        result = _render(data)
        assert "# Experience" in result
        assert "## Engineer" in result
        assert "## Developer" in result

    def test_list_of_dicts_with_document_title(self):
        data = {
            "_title": "Resume",
            "experience": [
                {"title": "Engineer", "company": "Acme"},
            ],
        }
        result = _render(data)
        assert "# Resume" in result
        assert "## Experience" in result
        assert "### Engineer" in result

    def test_list_of_dicts_fallback_title(self):
        data = {"items": [{"value": "one"}, {"value": "two"}]}
        result = _render(data)
        assert "## Item 1" in result
        assert "## Item 2" in result

    def test_omits_none_values(self):
        data = {"present": "yes", "missing": None}
        result = _render(data)
        assert "**Present:** yes" in result
        assert "Missing" not in result

    def test_omits_empty_string_values(self):
        data = {"present": "yes", "empty": ""}
        result = _render(data)
        assert "**Present:** yes" in result
        assert "Empty" not in result

    def test_omits_empty_list_values(self):
        data = {"present": "yes", "empty_list": []}
        result = _render(data)
        assert "**Present:** yes" in result
        assert "Empty List" not in result

    def test_url_in_string_value_linkified(self):
        data = {"url": "https://example.com/job/123"}
        result = _render(data)
        assert "[https://example.com/job/123](https://example.com/job/123)" in result

    def test_long_string_as_block(self):
        long_text = "This is a very long description that exceeds eighty characters and should be rendered as a block instead of inline."
        data = {"description": long_text}
        result = _render(data)
        assert "**Description:**\n\n" in result
        assert long_text in result

    def test_numeric_value(self):
        data = {"count": 42}
        result = _render(data)
        assert "**Count:** 42" in result

    def test_boolean_value(self):
        data = {"active": True}
        result = _render(data)
        assert "**Active:** True" in result


class TestConvertWithPydantic:
    def test_accepts_unknown_pydantic_model(self):
        class SimpleModel(BaseModel):
            name: str
            value: int

        converter = MarkdownConverter()
        model = SimpleModel(name="Test", value=123)
        result = converter.convert(model)
        assert "**Name:** Test" in result
        assert "**Value:** 123" in result


class TestConvertJobPosting:
    @pytest.fixture
    def converter(self):
        return MarkdownConverter()

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

    def test_title_includes_company(self, converter, sample_job_posting):
        result = converter.convert(sample_job_posting)
        assert "# Software Engineer at Acme Corp\n" in result

    def test_title_omits_not_specified_company(self, converter):
        job = JobPosting(
            url="https://example.com/job/456",
            company="Not specified",
            title="Developer",
            industry="Tech",
            description="A job",
            experience_level="Senior",
        )
        result = converter.convert(job)
        assert "# Developer\n" in result
        assert "at Not specified" not in result

    def test_includes_responsibilities(self, converter, sample_job_posting):
        result = converter.convert(sample_job_posting)
        assert "- Write code" in result
        assert "- Review PRs" in result

    def test_includes_skills(self, converter, sample_job_posting):
        result = converter.convert(sample_job_posting)
        assert "- Python" in result
        assert "- Testing" in result


class TestConvertCv:
    @pytest.fixture
    def converter(self):
        return MarkdownConverter()

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
            summary_of_qualifications=["10 years experience"],
            education=[],
            experience=[],
            additional_experience=[],
            areas_of_expertise=[],
            languages=[],
        )

    def test_title_is_name(self, converter, sample_cv):
        result = converter.convert(sample_cv)
        assert "# Jane Doe\n" in result

    def test_includes_profession(self, converter, sample_cv):
        result = converter.convert(sample_cv)
        assert "**Profession:** Software Engineer" in result

    def test_includes_contact(self, converter, sample_cv):
        result = converter.convert(sample_cv)
        assert "**Email:** jane@example.com" in result
        assert "**Location:** San Francisco, CA" in result

    def test_includes_core_expertise(self, converter, sample_cv):
        result = converter.convert(sample_cv)
        assert "- Python" in result
        assert "- Testing" in result
