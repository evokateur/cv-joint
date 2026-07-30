"""Registry mapping a document type to its default LaTeX template.

The template path is an explicit string (not derived from the type name) so the
flat `templates/*.tex` layout can later move to per-template directories as a
data-only change.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RenderSpec:
    """Default template for a renderable document type."""

    template: str


RENDERERS: dict[str, RenderSpec] = {
    "cv": RenderSpec(template="cv.tex"),
    "cover-letter": RenderSpec(template="cover-letter.tex"),
}

__all__ = ["RenderSpec", "RENDERERS"]
