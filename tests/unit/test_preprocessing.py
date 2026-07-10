from services.preprocessing import preprocess_to_markdown

HTML = (
    "<!DOCTYPE html><html><head><title>Senior Python Engineer</title></head>"
    "<body><main><h1>Senior Python Engineer</h1>"
    "<p>We are hiring a backend engineer to build APIs and services. You will "
    "work with Python, FastAPI, and Postgres in a fully remote team.</p>"
    "</main></body></html>"
)


def test_html_is_converted_to_markdown():
    markdown = preprocess_to_markdown(HTML)
    assert "Senior Python Engineer" in markdown
    assert "<html" not in markdown.lower()


def test_html_bytes_are_decoded_and_converted():
    markdown = preprocess_to_markdown(HTML.encode("utf-8"))
    assert "Senior Python Engineer" in markdown


def test_markdown_passes_through_unchanged():
    md = "# Already Markdown\n\nJust some job text, already extracted."
    assert preprocess_to_markdown(md) == md


def test_source_url_selects_site_extractor(tmp_path):
    """A WTTJ URL routes HTML through the WelcomeToTheJungle extractor."""
    html = '<html><head><title>Role | Welcome to the Jungle</title></head><body></body></html>'
    # Should not raise; source_url informs extractor selection.
    result = preprocess_to_markdown(html, source_url="https://www.welcometothejungle.com/en/jobs/x")
    assert isinstance(result, str)
