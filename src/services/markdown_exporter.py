from typing import Optional

from converters import to_markdown
from models import (
    JobPosting,
    JobPostingRecord,
    CurriculumVitae,
    CurriculumVitaeRecord,
)
from infrastructure import MarkdownWriter


class MarkdownExporter:
    """Converts domain objects to markdown and delegates writing to MarkdownWriter."""

    def __init__(self, repository, markdown_writer: MarkdownWriter):
        self.repository = repository
        self.markdown_writer = markdown_writer

    def export_job_posting(self, record: JobPostingRecord, job_posting: JobPosting):
        title = self._job_posting_title(job_posting)
        markdown = to_markdown(job_posting, title=title)
        self.markdown_writer.write_job_posting(record.identifier, markdown)

    def export_cv(self, record: CurriculumVitaeRecord, cv: CurriculumVitae):
        markdown = to_markdown(cv, title=cv.name)
        self.markdown_writer.write_cv(record.identifier, markdown)

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

    @staticmethod
    def _job_posting_title(job_posting: JobPosting) -> str:
        if job_posting.company and job_posting.company.lower() != "not specified":
            return f"{job_posting.title} at {job_posting.company}"
        return job_posting.title
