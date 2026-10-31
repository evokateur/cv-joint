import re
from typing import Optional

import yaml
from pydantic import BaseModel

from models import (
    CoverLetterRecord,
    JobPosting,
    JobPostingRecord,
    CvTransformationPlan,
    CurriculumVitae,
    CurriculumVitaeRecord,
    OptimizedCvRecord,
)
from .converters import MarkdownConverter, insert_json_as_frontmatter


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

    def _save(self, record: BaseModel, obj: BaseModel):
        markdown = self.converter.convert(obj)
        if markdown is None:
            return
        filename = f"{_to_kebab_case(type(obj).__name__)}.md"
        markdown = self.compose_document(record, filename, markdown)
        self.repository.add_or_replace_document(record, filename, markdown)

    def export_job_posting(self, record: JobPostingRecord, job_posting: JobPosting):
        self._save(record, job_posting)

    def export_cv(
        self, record: CurriculumVitaeRecord | OptimizedCvRecord, cv: CurriculumVitae
    ):
        self._save(record, cv)

    def export_cv_transformation_plan(
        self, record: OptimizedCvRecord, plan: CvTransformationPlan
    ):
        self._save(record, plan)

    def export(self, collection_name: Optional[str] = None) -> int:
        """Bulk export (regeneration). Iterates repository, exports each object."""
        if collection_name and collection_name not in (
            "job-postings",
            "cvs",
            "curriculum-vitae",
            "optimizations",
        ):
            raise ValueError(f"Unknown collection: {collection_name}")
        if collection_name == "curriculum-vitae":
            collection_name = "cvs"

        count = 0
        if collection_name is None or collection_name == "job-postings":
            for record in self.repository.get_job_posting_records(all=True):
                job_posting = self.repository.get_job_posting(record.identifier)
                self.export_job_posting(record, job_posting)
                count += 1
        if collection_name is None or collection_name == "cvs":
            for record in self.repository.get_cv_records():
                cv = self.repository.get_cv(record.identifier)
                self.export_cv(record, cv)
                count += 1
        if collection_name is None or collection_name == "optimizations":
            for record in self.repository.get_optimized_cv_records():
                cv = self.repository.get_optimized_cv(
                    record.job_posting_identifier, record.identifier
                )
                if cv:
                    self.export_cv(record, cv)
                    count += 1
                for obj in self.repository.load_all_objects(record).values():
                    if isinstance(obj, CurriculumVitae):
                        continue  # already exported via export_cv
                    self._save(record, obj)
                    count += 1
        return count
