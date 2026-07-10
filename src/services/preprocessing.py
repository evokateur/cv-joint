"""Preprocess raw job-posting content into clean markdown.

HTML is converted via the vendored post-extractor stack (site-specific
extractors, then a generic fallback). Non-HTML content is assumed to be
markdown already and passed through unchanged. The goal is simply: get to
markdown before the analysis crew sees the content.
"""

import post_extractor

__all__ = ["preprocess_to_markdown"]

_HTML_MARKERS = ("<html", "<!doctype", "<head")


def _looks_like_html(text: str) -> bool:
    """Sniff the leading bytes for an HTML document marker."""
    head = text[:512].lower()
    return any(marker in head for marker in _HTML_MARKERS)


def preprocess_to_markdown(content: bytes | str, source_url: str | None = None) -> str:
    """Convert HTML content to markdown; pass non-HTML through unchanged.

    Args:
        content: raw source content (bytes from a fetch/file read, or text)
        source_url: the posting URL, used to select the right site extractor
            and resolve relative links

    Returns:
        markdown text
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    if _looks_like_html(content):
        return post_extractor.extract_job_posting(
            content, source_url=source_url
        ).to_markdown()
    return content
