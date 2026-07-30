"""Registry mapping a document type to its schema and default LaTeX template.

The template path is an explicit string (not derived from the type name) so the
flat `templates/*.tex` layout can later move to per-template directories as a
data-only change.
"""

from dataclasses import dataclass
from typing import Type

from pydantic import BaseModel

from models.schema import CoverLetter, CurriculumVitae


@dataclass(frozen=True)
class RenderSpec:
    """Schema and default template for a renderable document type."""

    schema: Type[BaseModel]
    template: str


RENDERERS: dict[str, RenderSpec] = {
    "cv": RenderSpec(schema=CurriculumVitae, template="cv.tex"),
    "cover-letter": RenderSpec(schema=CoverLetter, template="cover-letter.tex"),
}

__all__ = ["RenderSpec", "RENDERERS"]
