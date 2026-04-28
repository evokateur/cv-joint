from typing import Optional

from models import (
    JobPosting,
    JobPostingRecord,
    CvTransformationPlan,
    CurriculumVitae,
    CurriculumVitaeRecord,
    OptimizedCvRecord,
)
from infrastructure import MarkdownWriter
from .converters import MarkdownConverter


class MarkdownExporter:
    """Delegates markdown conversion and writes results to the filesystem."""

    def __init__(
        self, repository, markdown_writer: MarkdownWriter, converter: MarkdownConverter
    ):
        self.repository = repository
        self.markdown_writer = markdown_writer
        self.converter = converter

    def export_job_posting(self, record: JobPostingRecord, job_posting: JobPosting):
        markdown = self.converter.convert_job_posting(job_posting, record)
        self.markdown_writer.write_job_posting(record.identifier, markdown)

    def export_cv(
        self, record: CurriculumVitaeRecord | OptimizedCvRecord, cv: CurriculumVitae
    ):
        markdown = self.converter.convert_cv(cv, record)
        if isinstance(record, CurriculumVitaeRecord):
            self.markdown_writer.write_cv(record.identifier, markdown)
        elif isinstance(record, OptimizedCvRecord):
            self.markdown_writer.write_optimized_cv(
                record.job_posting_identifier, record.identifier, markdown
            )

    def export_cv_transformation_plan(
        self, record: OptimizedCvRecord, plan: CvTransformationPlan
    ):
        markdown = self.converter.convert_transformation_plan(plan, record)
        self.markdown_writer.write_cv_transformation_plan(
            record.job_posting_identifier, record.identifier, markdown
        )

    def export(self, collection_name: Optional[str] = None) -> int:
        """Bulk export (regeneration). Iterates repository, exports each object."""
        if collection_name and collection_name not in ("job-postings", "cvs", "optimizations"):
            raise ValueError(f"Unknown collection: {collection_name}")

        count = 0
        if collection_name is None or collection_name == "job-postings":
            for item in self.repository.list_job_postings():
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
                cv = self.repository.get_optimized_cv(
                    record.job_posting_identifier, record.identifier
                )
                base_uri = f"job-postings/{record.job_posting_identifier}/cvs/{record.identifier}"
                plan = self.repository.load_object(base_uri, CvTransformationPlan)
                if cv:
                    self.export_cv(record, cv)
                    count += 1
                if plan:
                    self.export_cv_transformation_plan(record, plan)
                    count += 1
        return count
