import re
from typing import Any, Union

from pydantic import BaseModel

URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


def to_markdown(
    data: Union[dict, BaseModel],
    title: str | None = None,
    level: int = 1,
) -> str:
    """
    Convert any dict or Pydantic model to markdown.

    Args:
        data: Dict or Pydantic model to convert
        title: Optional title for the document
        level: Starting header level (1 = #, 2 = ##, etc.)

    Returns:
        Markdown string representation
    """
    if isinstance(data, BaseModel):
        data = data.model_dump()

    lines = []
    if title:
        lines.append(f"{'#' * level} {title}\n")
        level += 1

    for key, value in data.items():
        heading = _key_to_heading(key)
        formatted = _format_field(heading, value, level)
        if formatted:
            lines.append(formatted)

    return "\n".join(lines)


def _key_to_heading(key: str) -> str:
    """Convert snake_case to Title Case."""
    return key.replace("_", " ").title()


def _format_field(name: str, value: Any, level: int) -> str:
    """Format a single field as markdown."""
    if value is None or value == "" or value == []:
        return ""

    if isinstance(value, str):
        value = _linkify_urls(value)
        if len(value) < 80 and "\n" not in value:
            return f"**{name}:** {value}\n"
        return f"**{name}:**\n\n{value}\n"

    if isinstance(value, list):
        if not value:
            return ""
        if all(isinstance(item, str) for item in value):
            items = "\n".join(f"- {_linkify_urls(item)}" for item in value)
            return f"**{name}:**\n\n{items}\n"
        parts = [f"{'#' * level} {name}\n"]
        for i, item in enumerate(value):
            if isinstance(item, dict):
                sub_title = _extract_title(item) or f"Item {i + 1}"
                parts.append(to_markdown(item, title=sub_title, level=level + 1))
        return "\n".join(parts)

    if isinstance(value, dict):
        return f"{'#' * level} {name}\n\n{to_markdown(value, level=level + 1)}"

    return f"**{name}:** {value}\n"


def _linkify_urls(text: str) -> str:
    """Convert URLs in text to markdown links."""
    def replace(match):
        url = match.group(0)
        display = url if len(url) < 60 else url[:57] + "..."
        return f"[{display}]({url})"
    return URL_PATTERN.sub(replace, text)


def _extract_title(obj: dict) -> str | None:
    """Extract a reasonable title from an object."""
    for field in ("title", "name", "company", "degree", "language"):
        if field in obj and obj[field]:
            return obj[field]
    return None
