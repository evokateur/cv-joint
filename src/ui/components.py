import re

_FRONTMATTER_RE = re.compile(r"^(---\n.*?\n---)\n", re.DOTALL)


def front_matter_to_code_block(value: str) -> str:
    """Replace YAML front matter with a fenced code block for display in gr.Markdown."""
    if not value:
        return value
    match = _FRONTMATTER_RE.match(value)
    if not match:
        return value
    return f"```yaml\n{match.group(1)}\n```\n" + value[match.end():]
