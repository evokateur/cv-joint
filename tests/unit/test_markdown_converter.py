import pytest
from pydantic import BaseModel

from converters.markdown import to_markdown, _key_to_heading, _linkify_urls


class TestKeyToHeading:
    def test_converts_snake_case(self):
        assert _key_to_heading("technical_skills") == "Technical Skills"

    def test_converts_single_word(self):
        assert _key_to_heading("title") == "Title"

    def test_converts_multiple_underscores(self):
        assert _key_to_heading("summary_of_qualifications") == "Summary Of Qualifications"


class TestLinkifyUrls:
    def test_linkifies_https_url(self):
        result = _linkify_urls("Visit https://example.com for more")
        assert result == "Visit [https://example.com](https://example.com) for more"

    def test_linkifies_http_url(self):
        result = _linkify_urls("See http://example.com")
        assert result == "See [http://example.com](http://example.com)"

    def test_truncates_long_url_display(self):
        long_url = "https://example.com/very/long/path/that/exceeds/sixty/characters/total"
        result = _linkify_urls(long_url)
        # Display text is first 57 chars + "..."
        assert "[https://example.com/very/long/path/that/exceeds/sixty/cha...]" in result
        assert result.endswith(f"]({long_url})")

    def test_preserves_text_without_urls(self):
        text = "No URLs here, just plain text"
        assert _linkify_urls(text) == text

    def test_linkifies_multiple_urls(self):
        text = "See https://one.com and https://two.com"
        result = _linkify_urls(text)
        assert "[https://one.com](https://one.com)" in result
        assert "[https://two.com](https://two.com)" in result


class TestToMarkdown:
    def test_simple_string_values(self):
        data = {"title": "Engineer", "company": "Acme"}
        result = to_markdown(data)
        assert "**Title:** Engineer" in result
        assert "**Company:** Acme" in result

    def test_with_title(self):
        data = {"name": "Test"}
        result = to_markdown(data, title="My Document")
        assert result.startswith("# My Document\n")

    def test_with_custom_level(self):
        data = {"name": "Test"}
        result = to_markdown(data, title="Subsection", level=2)
        assert result.startswith("## Subsection\n")

    def test_list_of_strings_as_bullets(self):
        data = {"skills": ["Python", "Go", "Rust"]}
        result = to_markdown(data)
        assert "**Skills:**" in result
        assert "- Python" in result
        assert "- Go" in result
        assert "- Rust" in result

    def test_nested_dict_as_subsection(self):
        data = {"contact": {"email": "test@example.com", "phone": "555-1234"}}
        result = to_markdown(data)
        # Without a title, level starts at 1, so nested dict uses # (level 1)
        assert "# Contact" in result
        assert "**Email:** test@example.com" in result
        assert "**Phone:** 555-1234" in result

    def test_nested_dict_with_title_uses_higher_level(self):
        data = {"contact": {"email": "test@example.com"}}
        result = to_markdown(data, title="Person")
        # With title at level 1, nested dict uses ## (level 2)
        assert "# Person" in result
        assert "## Contact" in result

    def test_list_of_dicts_with_title_extraction(self):
        data = {
            "experience": [
                {"title": "Engineer", "company": "Acme"},
                {"title": "Developer", "company": "Beta"},
            ]
        }
        result = to_markdown(data)
        # Without document title, level=1: section header is #, items are ##
        assert "# Experience" in result
        assert "## Engineer" in result
        assert "## Developer" in result

    def test_list_of_dicts_with_document_title(self):
        data = {
            "experience": [
                {"title": "Engineer", "company": "Acme"},
            ]
        }
        result = to_markdown(data, title="Resume")
        # With document title at level 1, section is ##, items are ###
        assert "# Resume" in result
        assert "## Experience" in result
        assert "### Engineer" in result

    def test_list_of_dicts_fallback_title(self):
        data = {"items": [{"value": "one"}, {"value": "two"}]}
        result = to_markdown(data)
        # Without document title, items use ## with fallback "Item N" title
        assert "## Item 1" in result
        assert "## Item 2" in result

    def test_omits_none_values(self):
        data = {"present": "yes", "missing": None}
        result = to_markdown(data)
        assert "**Present:** yes" in result
        assert "Missing" not in result

    def test_omits_empty_string_values(self):
        data = {"present": "yes", "empty": ""}
        result = to_markdown(data)
        assert "**Present:** yes" in result
        assert "Empty" not in result

    def test_omits_empty_list_values(self):
        data = {"present": "yes", "empty_list": []}
        result = to_markdown(data)
        assert "**Present:** yes" in result
        assert "Empty List" not in result

    def test_url_in_string_value_linkified(self):
        data = {"url": "https://example.com/job/123"}
        result = to_markdown(data)
        assert "[https://example.com/job/123](https://example.com/job/123)" in result

    def test_long_string_as_block(self):
        long_text = "This is a very long description that exceeds eighty characters and should be rendered as a block instead of inline."
        data = {"description": long_text}
        result = to_markdown(data)
        assert "**Description:**\n\n" in result
        assert long_text in result

    def test_numeric_value(self):
        data = {"count": 42}
        result = to_markdown(data)
        assert "**Count:** 42" in result

    def test_boolean_value(self):
        data = {"active": True}
        result = to_markdown(data)
        assert "**Active:** True" in result


class TestToMarkdownWithPydantic:
    def test_accepts_pydantic_model(self):
        class SimpleModel(BaseModel):
            name: str
            value: int

        model = SimpleModel(name="Test", value=123)
        result = to_markdown(model)
        assert "**Name:** Test" in result
        assert "**Value:** 123" in result

    def test_pydantic_model_with_title(self):
        class SimpleModel(BaseModel):
            field: str

        model = SimpleModel(field="data")
        result = to_markdown(model, title="Model Output")
        assert "# Model Output" in result
        assert "**Field:** data" in result
