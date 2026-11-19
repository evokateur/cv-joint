import logging
import re
from typing import Optional

import yaml
from pydantic import BaseModel, ValidationError

from models import (
    CoverLetter,
    CoverLetterRecord,
    JobPosting,
    JobPostingRecord,
    CvTransformationPlan,
    CurriculumVitae,
    CurriculumVitaeRecord,
    OptimizedCvRecord,
)
from .converters import MarkdownConverter, insert_json_as_frontmatter

logger = logging.getLogger(__name__)

PLAN_FILENAME = "cv-transformation-plan.json"


def parse_transformation_plan(content, source: str) -> Optional[CvTransformationPlan]:
    """A transformation plan from JSON text or data, or None if it doesn't parse."""
    try:
        if isinstance(content, (str, bytes)):
            return CvTransformationPlan.model_validate_json(content)
        return CvTransformationPlan.model_validate(content)
    except ValidationError:
        logger.warning(
            "Skipping %s of %s: not a transformation plan", PLAN_FILENAME, source
        )
        return None


def read_transformation_plan(
    repository, record: OptimizedCvRecord
) -> Optional[CvTransformationPlan]:
    """An optimized CV's transformation plan, found by filename, if it parses."""
    if not repository.document_exists(record, PLAN_FILENAME):
        return None
    return parse_transformation_plan(
        repository.load_document(record, PLAN_FILENAME), record.identifier
    )


RECORD_DOCUMENTS: dict[type, set[str]] = {
    JobPostingRecord: {"job-posting"},
    CurriculumVitaeRecord: {"curriculum-vitae"},
    OptimizedCvRecord: {"curriculum-vitae", "cv-transformation-plan"},
    CoverLetterRecord: {"cover-letter"},
}


def _to_kebab_case(name: str) -> str:
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1-\2", s1).lower()


class MarkdownExporter:
    """Converts domain objects to markdown and writes them via the repository."""

    def __init__(self, repository, converter: MarkdownConverter):
        self.repository = repository
        self.converter = converter

    def compose_document(self, record: BaseModel, filename: str, content: str) -> str:
        """Prepend record metadata to its owned Markdown documents."""
        if filename.endswith(".md"):
            if filename[:-3] in RECORD_DOCUMENTS.get(type(record), set()):
                return insert_json_as_frontmatter(
                    record.model_dump(mode="json"), content
                )
        return content

    def patch_document_frontmatter(self, record: BaseModel) -> None:
        """Update existing record metadata while preserving custom keys and body."""
        for stem in RECORD_DOCUMENTS.get(type(record), set()):
            filename = f"{stem}.md"
            if not self.repository.document_exists(record, filename):
                continue
            content = self.repository.load_document(record, filename)
            if not content.startswith("---\n"):
                continue
            end = content.find("\n---\n", 4)
            if end == -1:
                continue
            existing = yaml.safe_load(content[4:end]) or {}
            body = content[end + 5 :]
            existing.update(record.model_dump(mode="json"))
            new_fm = f"---\n{yaml.dump(existing, default_flow_style=False, allow_unicode=True, sort_keys=False)}---\n"
            self.repository.add_or_replace_document(record, filename, new_fm + body)

    def _save(self, record: BaseModel, obj: BaseModel) -> int:
        markdown = self.converter.convert(obj)
        if markdown is None:
            return 0
        filename = f"{_to_kebab_case(type(obj).__name__)}.md"
        markdown = self.compose_document(record, filename, markdown)
        self.repository.add_or_replace_document(record, filename, markdown)
        return 1

    def export(self, records) -> int:
        """Regenerate Markdown for the selected records and their supported outputs."""
        count = 0
        for record in records:
            if isinstance(record, JobPostingRecord):
                model = JobPosting
            elif isinstance(record, CoverLetterRecord):
                model = CoverLetter
            else:
                model = CurriculumVitae
            content = self.repository.load_object(record, model)
            if content is None:
                raise FileNotFoundError(f"Content not found: {record.identifier}")
            count += self._save(record, content)
            if isinstance(record, OptimizedCvRecord):
                plan = read_transformation_plan(self.repository, record)
                if plan is not None:
                    count += self._save(record, plan)
        return count
