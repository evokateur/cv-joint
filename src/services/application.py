import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from config.root import get_settings
from models import CurriculumVitae, CvTransformationPlan, JobPosting
from services.analyzers import JobPostingAnalyzer
from services.analyzers import CvAnalyzer
from services.analyzers import CvOptimizer
from .converters import MarkdownConverter, insert_json_as_frontmatter
from .exporters import MarkdownExporter
from .preprocessing import preprocess_to_markdown
from repositories import FileSystemRepository
from repositories.filesystem import parse_uri
from renderers.latex import render_latex, latex_to_pdf


def _next_identifier(identifier: str, exists: Callable[[str], Any]) -> str:
    stripped = re.sub(r"-\d+$", "", identifier)
    base = stripped if stripped != identifier and exists(stripped) else identifier
    counter = 2
    candidate = f"{base}-{counter}"
    while exists(candidate):
        counter += 1
        candidate = f"{base}-{counter}"
    return candidate


class ApplicationService:
    """
    Application service for CV Joint operations.
    """

    def __init__(
        self,
        repository: Optional[FileSystemRepository] = None,
    ):
        self.job_posting_analyzer = JobPostingAnalyzer()
        self.cv_analyzer = CvAnalyzer()
        self.cv_optimizer = CvOptimizer()
        if repository is None:
            settings = get_settings()
            repository = FileSystemRepository(
                data_dir=settings.repositories.filesystem.data_dir
            )
        self.repository = repository
        self.markdown_converter = MarkdownConverter()
        self.markdown_exporter = MarkdownExporter(
            self.repository, self.markdown_converter
        )

    def extract_job_posting(
        self, url: str, content_file: Optional[str] = None
    ) -> str:
        """Resolve source content to clean markdown.

        Reads content_file when given, otherwise fetches the URL. HTML is
        converted to markdown via the post-extractor stack; already-markdown
        content passes through. The URL is threaded as source_url so the right
        site extractor is selected and relative links resolve.
        """
        if content_file is not None:
            content: bytes | str = Path(content_file).read_bytes()
        else:
            import requests

            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            content = resp.content
        return preprocess_to_markdown(content, source_url=url)

    def analyze_job_posting(self, url: str, markdown: str) -> JobPosting:
        """Analyze already-markdown content into a structured JobPosting.

        The URL is handed to the crew only so it does not fabricate one for the
        required url field; the caller stamps the authoritative URL onto the
        result. The markdown lives in a context-managed temp file for the
        duration of the analysis, then is cleaned up automatically.
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", encoding="utf-8"
        ) as tmp:
            tmp.write(markdown)
            tmp.flush()
            return self.job_posting_analyzer.analyze(tmp.name, url)

    def create_job_posting(
        self, url: str, content_file: Optional[str] = None
    ) -> tuple[dict[str, Any], str, str]:
        """
        Analyze a job posting and create a structured JobPosting.

        Note: This only analyzes, does not save. Use save_job_posting to persist
        the record and save_job_posting_source to persist the source markdown.

        Args:
            url: Job posting URL — its identity, used for dedup and stored as
                provenance. Content is fetched from this URL unless content_file
                is supplied (e.g. sites that only yield content in a browser).
            content_file: Local file path to analyze in lieu of fetching the URL

        Returns:
            tuple of (job_posting_data, suggested_identifier, source_markdown)
        """
        existing = self.repository.get_job_posting_record_by_url(url)
        if existing:
            raise ValueError(f"Job posting already analyzed: {existing.identifier}")

        source_markdown = self.extract_job_posting(url, content_file)
        job_posting = self.analyze_job_posting(url, source_markdown)

        job_posting = job_posting.model_copy(update={"url": url})
        identifier = self._generate_job_identifier(
            job_posting.company, job_posting.title
        )
        return job_posting.model_dump(), identifier, source_markdown

    def save_job_posting(self, job_posting_data: dict[str, Any], identifier: str):
        """
        Save a job posting to the repository.

        Handles identifier collisions by appending a number suffix if the
        identifier already exists. This allows re-analyzing the same job posting
        (e.g., after KB changes, prompt updates, or job posting changes) without
        overwriting the previous analysis.

        Args:
            job_posting_data: Job posting data dict (from create_job_posting)
            identifier: Identifier to use for this job posting

        Returns:
            JobPostingRecord
        """
        from models import JobPosting

        job_posting = JobPosting(**job_posting_data)

        if self.repository.get_job_posting(identifier):
            identifier = _next_identifier(identifier, self.repository.get_job_posting)

        record = self.repository.add_job_posting(job_posting, identifier)
        self.markdown_exporter.export_job_posting(record, job_posting)
        return record

    def _generate_job_identifier(self, company: str, title: str) -> str:
        """Generate a URL-safe identifier from company and title."""
        import re

        def slugify(text: str) -> str:
            text = text.lower()
            text = re.sub(r"[^\w\s-]", "", text)
            text = re.sub(r"[-\s]+", "-", text)
            return text.strip("-")

        if company.lower() == "not specified":
            return slugify(title)
        return f"{slugify(company)}-{slugify(title)}"

    def find_job_posting_by_url(self, url: str):
        """Find a job posting record by URL, or None if not found."""
        return self.repository.get_job_posting_record_by_url(url)

    def get_job_posting(self, identifier: str):
        """Retrieve a job posting by identifier."""
        return self.repository.get_job_posting(identifier)

    def get_job_postings(
        self, location: str | None = None, all: bool = False, query: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieve saved job postings.

        Args:
            location: Filter by location. None (default) returns active/unfiled only.
            all: If True and location is None, return all records across all locations.
            query: Optional keyword to filter by company, title, or experience level.

        Returns:
            list of job posting metadata dictionaries
        """
        results = self.repository.list_job_postings(location=location, all=all)
        if query:
            q = query.lower()
            results = [
                r for r in results
                if any(
                    q in (r.get(f) or "").lower()
                    for f in ("company", "title", "experience_level", "url", "created_at")
                )
            ]
        return results

    def transition_job_posting(
        self, identifier: str, location: str, fields: dict | None = None
    ):
        """File a job posting into a named location, recording the transition."""
        return self.repository.transition_job_posting(identifier, location, fields)

    def archive_job_posting(self, identifier: str):
        """Mark a job posting as archived."""
        return self.repository.archive_job_posting(identifier)

    def unarchive_job_posting(self, identifier: str):
        """Return a job posting to the root (active/unfiled)."""
        return self.repository.unarchive_job_posting(identifier)

    def mark_applied(
        self, identifier: str, cv_identifier: str, applied_at: Optional[datetime] = None
    ):
        """Record that a job posting was applied to with a given CV."""
        return self.repository.mark_applied(identifier, cv_identifier, applied_at=applied_at)

    def create_cv(
        self, content_file: Optional[str] = None
    ) -> tuple[dict[str, Any], str]:
        """
        Analyze a CV and create a structured CurriculumVitae.

        Note: This only analyzes, does not save. Use save_cv to persist.

        Args:
            content_file: Path to CV file (JSON, YAML, plain text, etc.)

        Returns:
            tuple of (cv_data, suggested_identifier)
        """
        if content_file is None:
            raise ValueError("content_file must be provided")
        cv = self.cv_analyzer.analyze(content_file)
        identifier = self._generate_cv_identifier(cv.profession)
        return cv.model_dump(), identifier

    def save_cv(self, cv_data: dict[str, Any], identifier: str):
        """
        Save a CV to the repository.

        Handles identifier collisions by appending a number suffix if the
        identifier already exists.

        Args:
            cv_data: CV data dict (from create_cv)
            identifier: Identifier to use for this CV

        Returns:
            CurriculumVitaeRecord
        """
        from models import CurriculumVitae

        cv = CurriculumVitae(**cv_data)

        if self.repository.get_cv(identifier):
            identifier = _next_identifier(identifier, self.repository.get_cv)

        record = self.repository.add_cv(cv, identifier)
        self.markdown_exporter.export_cv(record, cv)
        return record

    def _generate_cv_identifier(self, profession: str) -> str:
        """Generate a URL-safe identifier from profession."""
        import re

        def slugify(text: str) -> str:
            text = text.lower()
            text = re.sub(r"[^\w\s-]", "", text)
            text = re.sub(r"[-\s]+", "-", text)
            return text.strip("-")

        return slugify(profession)

    def get_cv(self, identifier: str):
        """Retrieve a CV by identifier."""
        return self.repository.get_cv(identifier)

    def get_cvs(self, query: str | None = None) -> list[dict[str, Any]]:
        """
        Retrieve all saved CVs.

        Returns:
            list of CV metadata dictionaries
        """
        results = self.repository.list_cvs()
        if query:
            q = query.lower()
            results = [
                r for r in results
                if any(q in (r.get(f) or "").lower() for f in ("name", "identifier"))
            ]
        return results

    def reanalyze_job_posting(self, identifier: str, content_file: Optional[str] = None):
        """
        Re-analyze a job posting and save as a new record with a suffix (e.g. acme-swe-2),
        preserving the original. Uses stored URL as fallback when no content_file is given.

        Args:
            identifier: Identifier of the job posting to re-analyze
            content_file: Local file path to use as content; fetches stored URL if omitted

        Returns:
            JobPostingRecord

        Raises:
            ValueError: If job posting not found or no content source available
        """
        record = self.repository.get_job_posting_record(identifier)
        if record is None:
            raise ValueError(f"Job posting not found: {identifier}")

        if content_file is None and not record.url:
            raise ValueError(
                f"No content file provided and no URL stored for {identifier}"
            )

        source_markdown = self.extract_job_posting(record.url, content_file)
        job_posting = self.analyze_job_posting(record.url, source_markdown)
        if record.url:
            job_posting = job_posting.model_copy(update={"url": record.url})

        new_identifier = _next_identifier(identifier, self.repository.get_job_posting_record)

        new_record = self.repository.add_job_posting(job_posting, new_identifier)
        self.markdown_exporter.export_job_posting(new_record, job_posting)
        return new_record

    def reanalyze_cv(self, identifier: str, content_file: str):
        """
        Re-analyze a CV from a source file and save as a new record with a suffix
        (e.g. jane-doe-2), preserving the original.

        Args:
            identifier: Identifier of the CV to re-analyze
            content_file: Path to CV file (JSON, YAML, or plain text)

        Returns:
            CurriculumVitaeRecord

        Raises:
            ValueError: If CV not found
        """
        if self.repository.get_cv_record(identifier) is None:
            raise ValueError(f"CV not found: {identifier}")

        cv = self.cv_analyzer.analyze(content_file)

        new_identifier = _next_identifier(identifier, self.repository.get_cv_record)

        new_record = self.repository.add_cv(cv, new_identifier)
        self.markdown_exporter.export_cv(new_record, cv)
        return new_record

    def reanalyze_cv_optimization(self, job_posting_identifier: str, identifier: str):
        """
        Re-run a CV optimization using its stored inputs and overwrite the existing record.

        Args:
            job_posting_identifier: Identifier of the parent job posting
            identifier: Identifier of the optimization

        Returns:
            CvOptimizationRecord

        Raises:
            ValueError: If CV optimization not found
        """
        record = self.repository.get_optimized_cv_record(job_posting_identifier, identifier)
        if record is None:
            raise ValueError(
                f"CV optimization not found: job-postings/{job_posting_identifier}/cvs/{identifier}"
            )

        cv = self.repository.get_cv(record.base_cv_identifier)
        job_posting = self.repository.get_job_posting(job_posting_identifier)

        if cv is None or job_posting is None:
            raise ValueError(
                f"Base CV or job posting missing for re-run: job-postings/{job_posting_identifier}/cvs/{identifier}"
            )

        output = self.cv_optimizer.optimize(cv, job_posting)

        new_identifier = _next_identifier(
            identifier,
            lambda id: self.repository.get_optimized_cv_record(job_posting_identifier, id),
        )

        self._write_optimization_outputs(job_posting_identifier, new_identifier, output)

        plan = output.artifacts.get("transformation-plan")
        if plan is None:
            raise ValueError(
                f"Optimization output missing after re-run: job-postings/{job_posting_identifier}/cvs/{new_identifier}"
            )

        new_record = self.repository.add_optimized_cv(
            job_posting_identifier, new_identifier, record.base_cv_identifier, output.cv
        )
        self.markdown_exporter.export_cv_transformation_plan(new_record, plan)
        self.markdown_exporter.export_cv(new_record, output.cv)
        return new_record

    def remove_job_posting(self, identifier: str) -> bool:
        """
        Remove a job posting and all nested cv optimizations.

        Args:
            identifier: Identifier of the job posting

        Returns:
            True if removed, False if not found
        """
        return self.repository.remove_job_posting(identifier)

    def remove_cv(self, identifier: str) -> bool:
        """
        Remove a CV.

        Args:
            identifier: Identifier of the CV

        Returns:
            True if removed, False if not found

        """
        return self.repository.remove_cv(identifier)

    def remove_cv_optimization(
        self, job_posting_identifier: str, identifier: str
    ) -> bool:
        """
        Remove a saved cv optimization.

        Args:
            job_posting_identifier: Identifier of the parent job posting
            identifier: Identifier of the optimization

        Returns:
            True if removed, False if not found
        """
        return self.repository.remove_optimized_cv(job_posting_identifier, identifier)

    def rename_job_posting(self, identifier: str, new_identifier: str):
        """
        Rename a job posting, moving its data and markdown to the new identifier.

        Raises:
            ValueError: If not found or new identifier already exists
        """
        return self.repository.rename_job_posting(identifier, new_identifier)

    def rename_cv(self, identifier: str, new_identifier: str):
        """
        Rename a CV, moving its data and markdown to the new identifier.
        Also repairs any cv optimization records that reference this CV.

        Raises:
            ValueError: If not found or new identifier already exists
        """
        return self.repository.rename_cv(identifier, new_identifier)

    def rename_cv_optimization(
        self, job_posting_identifier: str, identifier: str, new_identifier: str
    ):
        """
        Rename a CV optimization, moving its data and markdown to the new identifier.

        Raises:
            ValueError: If not found or new identifier already exists
        """
        return self.repository.rename_optimized_cv(
            job_posting_identifier, identifier, new_identifier
        )

    def export_markdown(self, collection_name: Optional[str] = None) -> int:
        """
        Re-export all markdown files from stored domain objects.

        This overwrites any existing markdown files, including manual edits.
        """
        return self.markdown_exporter.export(collection_name)

    def add_document(self, uri: str, file_path: str) -> str:
        """Place a file into an object's data directory. Returns the document URI."""
        try:
            parse_uri(uri)
            base_uri = uri
            doc_uri = f"{uri}/{Path(file_path).name}"
        except ValueError:
            base_uri, _ = uri.rsplit("/", 1)
            doc_uri = uri

        self.repository.resolve_record(base_uri)
        self.repository.save_document(doc_uri, Path(file_path).read_text())
        return doc_uri

    def create_cv_optimization(
        self, job_posting_identifier: str, cv_identifier: str
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        """
        Create a CV optimization for a job posting.

        Args:
            job_posting_identifier: Identifier of the job posting
            cv_identifier: Identifier of the base CV

        Returns:
            tuple of (plan_data, cv_data, identifiers_dict)
            where identifiers_dict contains job_posting_identifier, identifier, base_cv_identifier
        """
        import datetime

        cv = self.repository.get_cv(cv_identifier)
        job_posting = self.repository.get_job_posting(job_posting_identifier)

        if cv is None or job_posting is None:
            raise ValueError(
                f"CV or job posting not found: {cv_identifier}, {job_posting_identifier}"
            )

        identifier = f"{cv_identifier}-{datetime.date.today()}"

        output = self.cv_optimizer.optimize(cv, job_posting)
        plan = output.artifacts.get("transformation-plan")

        identifiers = {
            "job_posting_identifier": job_posting_identifier,
            "identifier": identifier,
            "base_cv_identifier": cv_identifier,
        }

        return (
            plan.model_dump() if plan else {},
            output.cv.model_dump(),
            identifiers,
        )

    def _write_optimization_outputs(
        self, job_posting_identifier: str, identifier: str, output
    ):
        """Write peripheral optimizer artifacts via the repository (class-name convention)."""
        base_uri = self.repository.optimized_cv_base_uri(job_posting_identifier, identifier)
        for artifact in output.artifacts.values():
            self.repository.save_object(base_uri, artifact)

    def save_cv_optimization(
        self,
        job_posting_identifier: str,
        identifier: str,
        base_cv_identifier: str,
        cv: CurriculumVitae,
        plan: CvTransformationPlan | None = None,
    ):
        """
        Save a CV optimization to the repository.

        Args:
            job_posting_identifier: Identifier of the job posting
            identifier: Identifier for this optimization
            base_cv_identifier: Identifier of the base CV
            cv: The optimized CV
            plan: The transformation plan, if any

        Returns:
            OptimizedCvRecord
        """
        record = self.repository.add_optimized_cv(
            job_posting_identifier, identifier, base_cv_identifier, cv
        )

        if plan is not None:
            base_uri = self.repository.optimized_cv_base_uri(job_posting_identifier, identifier)
            self.repository.save_object(base_uri, plan)
            self.markdown_exporter.export_cv_transformation_plan(record, plan)
        self.markdown_exporter.export_cv(record, cv)

        return record

    def get_cv_optimizations(self) -> list[dict[str, Any]]:
        """
        Retrieve saved cv optimizations, excluding those whose parent job posting is archived.

        Returns:
            list of optimization metadata dictionaries
        """
        opts = self.repository.list_optimized_cvs()
        active_job_ids = {
            item["identifier"] for item in self.repository.list_job_postings()
        }
        return [o for o in opts if o.get("job_posting_identifier") in active_job_ids]

    def get_cv_optimization(
        self, job_posting_identifier: str, identifier: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Retrieve a specific CV optimization (plan and cv) for viewing.

        Args:
            job_posting_identifier: Identifier of the job posting
            identifier: Identifier of the optimization

        Returns:
            tuple of (plan_data, cv_data)
        """
        base_uri = self.repository.optimized_cv_base_uri(job_posting_identifier, identifier)
        plan = self.repository.load_object(base_uri, CvTransformationPlan)
        cv = self.repository.get_optimized_cv(job_posting_identifier, identifier)

        return (
            plan.model_dump() if plan else {},
            cv.model_dump() if cv else {},
        )

    def purge_cv_optimization(
        self, job_posting_identifier: str, identifier: str
    ) -> bool:
        """
        Delete an unsaved CV optimization from disk without removing the collection record.

        Returns:
            True if deleted, False if not found
        """
        return self.repository.purge_optimized_cv(job_posting_identifier, identifier)

    def get_cv_data_filepaths(self) -> list[dict[str, Any]]:
        active_job_ids = {
            item["identifier"] for item in self.repository.list_job_postings()
        }
        results = []
        for item in self.repository.list_cvs():
            results.append({
                "identifier": item["identifier"],
                "filepath": str(self.repository.data_dir / item["path"] / "curriculum-vitae.json"),
            })
        for item in self.repository.list_optimized_cvs():
            if item.get("job_posting_identifier") in active_job_ids:
                jp_id = item["job_posting_identifier"]
                id_ = item["identifier"]
                filepath = str(
                    self.repository.data_dir
                    / "job-postings" / jp_id / "cvs" / id_ / "curriculum-vitae.json"
                )
                results.append({
                    "identifier": id_,
                    "job_posting_identifier": jp_id,
                    "filepath": filepath,
                })
        return results

    def get_cv_template_names(self) -> list[str]:
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent
        templates_dir = project_root / "templates"
        return [str(p.name) for p in templates_dir.glob("*cv*.tex")]

    def to_markdown(self, domain_object) -> str:
        return self.markdown_converter.convert(domain_object) or ""

    def get_display_markdown(self, uri: str, obj) -> str:
        base_uri = uri.rsplit("/", 1)[0]
        record = self.repository.resolve_record(base_uri)
        return insert_json_as_frontmatter(record.model_dump(mode="json"), self.to_markdown(obj))

    def get_job_posting_record(self, identifier: str):
        return self.repository.get_job_posting_record(identifier)

    def get_cv_record(self, identifier: str):
        return self.repository.get_cv_record(identifier)

    def get_optimized_cv_record(self, job_posting_identifier: str, identifier: str):
        return self.repository.get_optimized_cv_record(job_posting_identifier, identifier)

    def generate_pdf_file(self, data_path: str, template_name: str, stem: str = "output") -> str:
        tmp_dir = tempfile.mkdtemp()
        tex_path = str(Path(tmp_dir) / f"{stem}.tex")
        render_latex(data_path, tex_path, template_name)
        return latex_to_pdf(tex_path)
