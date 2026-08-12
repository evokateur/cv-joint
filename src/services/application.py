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
from repositories import FileSystemRepository
from repositories.filesystem import parse_uri
from renderers.latex import render_tex, tex_to_pdf


def _next_identifier(identifier: str, exists: Callable[[str], Any]) -> str:
    stripped = re.sub(r"-\d+$", "", identifier)
    base = stripped if stripped != identifier and exists(stripped) else identifier
    counter = 2
    candidate = f"{base}-{counter}"
    while exists(candidate):
        counter += 1
        candidate = f"{base}-{counter}"
    return candidate


def _slugify(text: str) -> str:
    """Lowercase, drop punctuation, and hyphenate whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")


def _slugify_job(company: str, title: str) -> str:
    if company.lower() == "not specified":
        return _slugify(title)
    return f"{_slugify(company)}-{_slugify(title)}"


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

    def object_exists(self, uri: str) -> bool:
        """Whether an object exists at uri. The collision check, keyed on the URI.

        Handles object URIs only (job-postings/{id}, cvs/{id},
        cover-letters/{id}, job-postings/{id}/cvs/{id}). Anything else — an
        unparseable or document URI — is reported as not existing.
        """
        try:
            parsed = parse_uri(uri)
        except ValueError:
            return False
        collection = parsed["collection"]
        if collection == "job-postings":
            return self.repository.get_job_posting(parsed["identifier"]) is not None
        if collection == "cvs":
            return self.repository.get_cv(parsed["identifier"]) is not None
        if collection == "cover-letters":
            return self.repository.get_cover_letter(parsed["identifier"]) is not None
        if collection == "optimized-cvs":
            return (
                self.repository.get_optimized_cv(
                    parsed["job_posting_identifier"], parsed["identifier"]
                )
                is not None
            )
        return False

    def unique_new_identifier(self, uri: str) -> str:
        """A free identifier in uri's namespace: its terminal segment, or a
        -N variant when that collides."""
        prefix, terminal = uri.rsplit("/", 1)

        def exists(identifier: str) -> bool:
            return self.object_exists(f"{prefix}/{identifier}")

        if not exists(terminal):
            return terminal
        return _next_identifier(terminal, exists)

    def generate_default_identifier(self, kind: str, data: dict[str, Any]) -> str:
        """A collision-free default identifier derived from an object's fields."""
        if kind == "job-postings":
            slug = _slugify_job(data["company"], data["title"])
        elif kind == "cvs":
            slug = _slugify(data["profession"])
        elif kind == "cover-letters":
            slug = "cover-letter"
        else:
            raise ValueError(f"no default identifier for {kind!r}")
        return self.unique_new_identifier(f"{kind}/{slug}")

    def _analyze_job_posting_url(self, url: str) -> JobPosting:
        """Fetch a URL and analyze its content as a job posting.

        The fetched content lives in a context-managed temp file for the
        duration of the analysis, then is cleaned up automatically.
        """
        import requests

        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".html") as tmp:
            tmp.write(resp.content)
            tmp.flush()
            return self.job_posting_analyzer.analyze(tmp.name)

    def analyze_job_posting(
        self, url: str, content_file: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Analyze a job posting into a structured JobPosting.

        Args:
            url: Job posting URL — stored as provenance. Content is fetched from
                this URL unless content_file is supplied (e.g. sites that only
                yield content in a browser). Re-analyzing the same URL is allowed.
            content_file: Local file path to analyze in lieu of fetching the URL

        Returns:
            job_posting_data; pass to add_job_posting (with an identifier) to persist.
        """
        if content_file is None:
            job_posting = self._analyze_job_posting_url(url)
        else:
            job_posting = self.job_posting_analyzer.analyze(content_file)

        job_posting = job_posting.model_copy(update={"url": url})
        return job_posting.model_dump()

    def add_job_posting(self, job_posting_data: dict[str, Any], identifier: str):
        """
        Add a job posting to the repository under identifier.

        Args:
            job_posting_data: Job posting data dict (from analyze_job_posting)
            identifier: Identifier to use for this job posting

        Returns:
            JobPostingRecord

        Raises:
            ValueError: if identifier already exists
        """
        from models import JobPosting

        job_posting = JobPosting(**job_posting_data)
        record = self.repository.add_job_posting(job_posting, identifier)
        self.markdown_exporter.export_job_posting(record, job_posting)
        return record

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
                r
                for r in results
                if any(
                    q in (r.get(f) or "").lower()
                    for f in (
                        "company",
                        "title",
                        "experience_level",
                        "url",
                        "created_at",
                    )
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
        return self.repository.transition_job_posting(
            identifier, "archived", record_fields={"is_archived": True}
        )

    def unarchive_job_posting(self, identifier: str):
        """Return a job posting to the root (active/unfiled)."""
        return self.repository.transition_job_posting(
            identifier, ".", record_fields={"is_archived": False}
        )

    def mark_applied(
        self, identifier: str, cv_identifier: str, applied_at: Optional[datetime] = None
    ):
        """Record that a job posting was applied to with a given CV."""
        applied_at_dt = applied_at or datetime.now()
        denorm = {
            "applied_with": cv_identifier,
            "applied_at": applied_at_dt.isoformat(),
        }
        return self.repository.transition_job_posting(
            identifier, "applied", fields=denorm, record_fields=denorm
        )

    def analyze_cv(
        self, content_file: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Analyze a CV into a structured CurriculumVitae.

        Args:
            content_file: Path to CV file (JSON, YAML, plain text, etc.)

        Returns:
            cv_data; pass to add_cv (with an identifier) to persist.
        """
        if content_file is None:
            raise ValueError("content_file must be provided")
        cv = self.cv_analyzer.analyze(content_file)
        return cv.model_dump()

    def add_cv(self, cv_data: dict[str, Any], identifier: str):
        """
        Add a CV to the repository under identifier.

        Args:
            cv_data: CV data dict (from analyze_cv)
            identifier: Identifier to use for this CV

        Returns:
            CurriculumVitaeRecord

        Raises:
            ValueError: if identifier already exists
        """
        from models import CurriculumVitae

        cv = CurriculumVitae(**cv_data)
        record = self.repository.add_cv(cv, identifier)
        self.markdown_exporter.export_cv(record, cv)
        return record

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
                r
                for r in results
                if any(q in (r.get(f) or "").lower() for f in ("name", "identifier"))
            ]
        return results

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
        self.repository.add_document(doc_uri, Path(file_path).read_text())
        return doc_uri

    def analyze_cv_optimization(
        self, job_posting_identifier: str, cv_identifier: str
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        """
        Analyze a CV optimization for a job posting.

        Args:
            job_posting_identifier: Identifier of the job posting
            cv_identifier: Identifier of the base CV

        Returns:
            tuple of (plan_data, cv_data, identifiers_dict); pass to add_cv_optimization to persist.
            identifiers_dict contains job_posting_identifier, identifier, base_cv_identifier
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

    def add_cv_optimization(
        self,
        job_posting_identifier: str,
        identifier: str,
        base_cv_identifier: str,
        cv: CurriculumVitae,
        plan: CvTransformationPlan | None = None,
    ):
        """
        Add a CV optimization to the repository.

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
            base_uri = self.repository.optimized_cv_base_uri(
                job_posting_identifier, identifier
            )
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
        base_uri = self.repository.optimized_cv_base_uri(
            job_posting_identifier, identifier
        )
        plan = self.repository.load_object(base_uri, CvTransformationPlan)
        cv = self.repository.get_optimized_cv(job_posting_identifier, identifier)

        return (
            plan.model_dump() if plan else {},
            cv.model_dump() if cv else {},
        )

    def get_cv_data_filepaths(self) -> list[dict[str, Any]]:
        active_job_ids = {
            item["identifier"] for item in self.repository.list_job_postings()
        }
        results = []
        for item in self.repository.list_cvs():
            results.append(
                {
                    "identifier": item["identifier"],
                    "filepath": str(
                        self.repository.data_dir
                        / item["path"]
                        / "curriculum-vitae.json"
                    ),
                }
            )
        for item in self.repository.list_optimized_cvs():
            if item.get("job_posting_identifier") in active_job_ids:
                jp_id = item["job_posting_identifier"]
                id_ = item["identifier"]
                filepath = str(
                    self.repository.data_dir
                    / "job-postings"
                    / jp_id
                    / "cvs"
                    / id_
                    / "curriculum-vitae.json"
                )
                results.append(
                    {
                        "identifier": id_,
                        "job_posting_identifier": jp_id,
                        "filepath": filepath,
                    }
                )
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
        return insert_json_as_frontmatter(
            record.model_dump(mode="json"), self.to_markdown(obj)
        )

    def get_job_posting_record(self, identifier: str):
        return self.repository.get_job_posting_record(identifier)

    def get_cv_record(self, identifier: str):
        return self.repository.get_cv_record(identifier)

    def get_optimized_cv_record(self, job_posting_identifier: str, identifier: str):
        return self.repository.get_optimized_cv_record(
            job_posting_identifier, identifier
        )

    def get_optimized_cv(self, job_posting_identifier: str, identifier: str):
        """Retrieve an optimized CV domain object by job posting and CV identifier."""
        return self.repository.get_optimized_cv(job_posting_identifier, identifier)

    def generate_pdf_file(
        self, data: dict[str, Any], template_name: str, output_path: str
    ) -> str:
        tex = render_tex(data, template_name)
        return tex_to_pdf(tex, output_path)
