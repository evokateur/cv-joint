from pathlib import Path
from typing import Optional

from converters import to_markdown
from config.settings import get_markdown_root


class MarkdownWriter:
    """Writes markdown files for domain objects alongside their JSON files."""

    def __init__(self, markdown_root: str = None):
        if markdown_root is None:
            markdown_root = get_markdown_root()

        self.markdown_root = Path(markdown_root).expanduser()

    def write(self, record_filepath: str, domain_object, title: str):
        """Write a markdown file alongside the JSON file for a domain object."""
        json_path = self.markdown_root / record_filepath
        md_path = json_path.with_suffix(".md")
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(to_markdown(domain_object, title=title))

    @staticmethod
    def job_posting_title(job_posting) -> str:
        """Build display title for a job posting."""
        if job_posting.company and job_posting.company.lower() != "not specified":
            return f"{job_posting.title} at {job_posting.company}"
        return job_posting.title

    def regenerate(self, repository, collection_name: Optional[str] = None) -> int:
        """
        Regenerate all markdown files from stored domain objects.

        This overwrites any existing markdown files, including manual edits.

        Args:
            repository: FileSystemRepository to load domain objects from
            collection_name: Optional "job-postings" or "cvs" to limit scope

        Returns:
            Number of markdown files written
        """
        if collection_name and collection_name not in ("job-postings", "cvs"):
            raise ValueError(f"Unknown collection: {collection_name}")

        count = 0
        if collection_name is None or collection_name == "job-postings":
            for item in repository.list_job_postings():
                job_posting = repository.get_job_posting(item["identifier"])
                self.write(
                    item["filepath"], job_posting, self.job_posting_title(job_posting)
                )
                count += 1
        if collection_name is None or collection_name == "cvs":
            for item in repository.list_cvs():
                cv = repository.get_cv(item["identifier"])
                self.write(item["filepath"], cv, cv.name)
                count += 1

        return count
