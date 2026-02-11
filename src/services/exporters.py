from typing import Optional

from models import (
    JobPosting,
    JobPostingRecord,
    CvOptimizationRecord,
    CvTransformationPlan,
    CurriculumVitae,
    CurriculumVitaeRecord,
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
        markdown = self.converter.convert(job_posting)
        self.markdown_writer.write_job_posting(record.identifier, markdown)

    def export_cv(
        self, record: CurriculumVitaeRecord | CvOptimizationRecord, cv: CurriculumVitae
    ):
        markdown = self.converter.convert(cv)
        if isinstance(record, CurriculumVitaeRecord):
            self.markdown_writer.write_cv(record.identifier, markdown)
        elif isinstance(record, CvOptimizationRecord):
            self.markdown_writer.write_optimized_cv(
                record.job_posting_identifier, record.identifier, markdown
            )

    def export_cv_transformation_plan(
        self, record: CvOptimizationRecord, plan: CvTransformationPlan
    ):
        markdown = self.converter.convert(plan)
        self.markdown_writer.write_cv_transformation_plan(
            record.job_posting_identifier, record.identifier, markdown
        )

    def export(self, collection_name: Optional[str] = None) -> int:
        """Bulk export (regeneration). Iterates repository, exports each object."""
        if collection_name and collection_name not in ("job-postings", "cvs"):
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
        return count
