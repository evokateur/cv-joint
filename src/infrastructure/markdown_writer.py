from pathlib import Path


class MarkdownWriter:
    """Writes markdown files to the filesystem.

    A pure filesystem adapter that receives markdown strings and identifiers,
    and knows the directory layout for each type of content.
    Argument names match filenames (e.g. job_posting -> job-posting.md).
    """

    def __init__(self, root_dir: str):
        if not root_dir:
            raise ValueError("MarkdownWriter root_dir is required")

        self.root_dir = Path(root_dir).expanduser()

    def write_job_posting(self, identifier: str, job_posting: str):
        md_path = self.root_dir / "job-postings" / identifier / "job-posting.md"
        self._write(md_path, job_posting)

    def write_cv(self, identifier: str, cv: str):
        md_path = self.root_dir / "cvs" / identifier / "cv.md"
        self._write(md_path, cv)

    def _write(self, path: Path, content: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
