import re
from typing import Optional

from pydantic import BaseModel

from models import (
    JobPosting,
    JobPostingRecord,
    CvTransformationPlan,
    CurriculumVitae,
    CurriculumVitaeRecord,
    OptimizedCvRecord,
)
from .converters import MarkdownConverter


def _to_kebab_case(name: str) -> str:
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1-\2", s1).lower()


class MarkdownExporter:
    """Converts domain objects to markdown and writes them via the repository."""

    def __init__(self, repository, converter: MarkdownConverter):
        self.repository = repository
        self.converter = converter

    def _save(self, base_uri: str, obj: BaseModel):
        markdown = self.converter.convert(obj)
        if markdown is None:
            return
        uri = f"{base_uri}/{_to_kebab_case(type(obj).__name__)}.md"
        self.repository.save_document(uri, markdown)

    def export_job_posting(self, record: JobPostingRecord, job_posting: JobPosting):
        self._save(f"job-postings/{record.identifier}", job_posting)

    def export_cv(
        self, record: CurriculumVitaeRecord | OptimizedCvRecord, cv: CurriculumVitae
    ):
        if isinstance(record, CurriculumVitaeRecord):
            base_uri = f"cvs/{record.identifier}"
        else:
            base_uri = f"job-postings/{record.job_posting_identifier}/cvs/{record.identifier}"
        self._save(base_uri, cv)

    def export_cv_transformation_plan(
        self, record: OptimizedCvRecord, plan: CvTransformationPlan
    ):
        base_uri = f"job-postings/{record.job_posting_identifier}/cvs/{record.identifier}"
        self._save(base_uri, plan)

    def export(self, collection_name: Optional[str] = None) -> int:
        """Bulk export (regeneration). Iterates repository, exports each object."""
        if collection_name and collection_name not in ("job-postings", "cvs", "curriculum-vitae", "optimizations"):
            raise ValueError(f"Unknown collection: {collection_name}")
        if collection_name == "curriculum-vitae":
            collection_name = "cvs"

        count = 0
        if collection_name is None or collection_name == "job-postings":
            for item in self.repository.list_job_postings(all=True):
                record = JobPostingRecord(**item)
                job_posting = self.repository.get_job_posting(record.identifier)
                self.export_job_posting(record, job_posting)
                count += 1
        if collection_name is None or collection_name == "cvs":
            for item in self.repository.list_cvs():
                record = CurriculumVitaeRecord(**item)
                cv = self.repository.get_cv(record.identifier)
                self.export_cv(record, cv)
                count += 1
        if collection_name is None or collection_name == "optimizations":
            for item in self.repository.list_optimized_cvs():
                record = OptimizedCvRecord(**item)
                uri = f"job-postings/{record.job_posting_identifier}/cvs/{record.identifier}"
                actual_path = self.repository.optimized_cv_base_uri(
                    record.job_posting_identifier, record.identifier
                )
                cv = self.repository.get_optimized_cv(
                    record.job_posting_identifier, record.identifier
                )
                if cv:
                    self.export_cv(record, cv)
                    count += 1
                for obj in self.repository.load_all_objects(actual_path).values():
                    if isinstance(obj, CurriculumVitae):
                        continue  # already exported via export_cv
                    self._save(uri, obj)
                    count += 1
        return count
