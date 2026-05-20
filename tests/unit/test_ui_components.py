from ui.components import front_matter_to_code_block

FRONTMATTER = """\
---
identifier: acme-engineer
company: Acme
created_at: '2026-01-01T00:00:00'
---
"""

BODY = "# Acme Engineer\n\nSome content."


def test_frontmatter_becomes_yaml_code_block():
    result = front_matter_to_code_block(FRONTMATTER + "\n" + BODY)
    assert result.startswith("```yaml\n---\n")
    assert "```" in result
    assert BODY in result


def test_no_frontmatter_passes_through():
    result = front_matter_to_code_block(BODY)
    assert result == BODY


def test_empty_string():
    result = front_matter_to_code_block("")
    assert result == ""
