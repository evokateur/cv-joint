import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from config.settings import get_data_dir
from models import CvTransformationPlan
from services.analyzers import JobPostingAnalyzer
from services.analyzers import CvAnalyzer
from services.analyzers import CvOptimizer
from .converters import MarkdownConverter
from .exporters import MarkdownExporter
from repositories import FileSystemRepository
from renderers.latex import render_latex, latex_to_pdf


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
        self.repository = repository or FileSystemRepository(data_dir=get_data_dir())
        self.markdown_converter = MarkdownConverter()
        self.markdown_exporter = MarkdownExporter(
            self.repository, self.markdown_converter
        )

    def create_job_posting(
        self, url: str, content_file: Optional[str] = None
    ) -> tuple[dict[str, Any], str]:
        """
        Analyze a job posting URL and create a structured JobPosting.

        Note: This only analyzes, does not save. Use save_job_posting to persist.

        Args:
            url: Job posting URL to analyze
            content_file: Optional local file path to use instead of fetching URL

        Returns:
            tuple of (job_posting_data, suggested_identifier)
        """
        existing = self.repository.get_job_posting_record_by_url(url)
        if existing:
            raise ValueError(
                f"Job posting already analyzed: {existing.identifier}"
            )

        job_posting = self.job_posting_analyzer.analyze(url, content_file)
        identifier = self._generate_job_identifier(
            job_posting.company, job_posting.title
        )
        return job_posting.model_dump(), identifier

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

        # Check for identifier collision
        if self.repository.get_job_posting(identifier):
            # Find next available identifier by appending number
            counter = 2
            original_identifier = identifier
            while True:
                candidate_identifier = f"{original_identifier}-{counter}"
                if not self.repository.get_job_posting(candidate_identifier):
                    identifier = candidate_identifier
                    break
                counter += 1

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
        self, archived: bool = False, query: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieve saved job postings.

        Args:
            archived: If False (default), excludes archived postings.
            query: Optional keyword to filter by company, title, or experience level.

        Returns:
            list of job posting metadata dictionaries
        """
        results = self.repository.list_job_postings(archived=archived)
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

    def archive_job_posting(self, identifier: str):
        """Mark a job posting as archived."""
        record = self.repository.archive_job_posting(identifier)
        job_posting = self.repository.get_job_posting(identifier)
        assert job_posting is not None
        self.markdown_exporter.export_job_posting(record, job_posting)
        return record

    def mark_applied(
        self, identifier: str, cv_identifier: str, applied_at: Optional[datetime] = None
    ):
        """Record that a job posting was applied to with a given CV."""
        record = self.repository.mark_applied(identifier, cv_identifier, applied_at=applied_at)
        job_posting = self.repository.get_job_posting(identifier)
        assert job_posting is not None
        self.markdown_exporter.export_job_posting(record, job_posting)
        return record

    def create_cv(self, file_path: str) -> tuple[dict[str, Any], str]:
        """
        Analyze a CV file and create a structured CurriculumVitae.

        Note: This only analyzes, does not save. Use save_cv to persist.

        Args:
            file_path: Path to CV file (JSON, YAML, or plain text)

        Returns:
            tuple of (cv_data, suggested_identifier)
        """
        cv = self.cv_analyzer.analyze(file_path)
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

        # Check for identifier collision
        if self.repository.get_cv(identifier):
            # Find next available identifier by appending number
            counter = 2
            original_identifier = identifier
            while True:
                candidate_identifier = f"{original_identifier}-{counter}"
                if not self.repository.get_cv(candidate_identifier):
                    identifier = candidate_identifier
                    break
                counter += 1

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
        Re-analyze a job posting from its stored URL and save as a new record with a
        suffix (e.g. acme-swe-2), preserving the original.

        Args:
            identifier: Identifier of the job posting to re-analyze
            content_file: Optional local file path to use instead of fetching the URL

        Returns:
            JobPostingRecord

        Raises:
            ValueError: If job posting not found
        """
        record = self.repository.get_job_posting_record(identifier)
        if record is None:
            raise ValueError(f"Job posting not found: {identifier}")

        job_posting = self.job_posting_analyzer.analyze(record.url, content_file)

        counter = 2
        new_identifier = f"{identifier}-{counter}"
        while self.repository.get_job_posting_record(new_identifier) is not None:
            counter += 1
            new_identifier = f"{identifier}-{counter}"

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

        counter = 2
        new_identifier = f"{identifier}-{counter}"
        while self.repository.get_cv_record(new_identifier) is not None:
            counter += 1
            new_identifier = f"{identifier}-{counter}"

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

        counter = 2
        new_identifier = f"{identifier}-{counter}"
        while self.repository.get_optimized_cv_record(job_posting_identifier, new_identifier) is not None:
            counter += 1
            new_identifier = f"{identifier}-{counter}"

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

        identifier = f"{datetime.date.today()}"
        base_uri = f"job-postings/{job_posting_identifier}/cvs/{identifier}"

        output = self.cv_optimizer.optimize(cv, job_posting)
        self.repository.save_object(base_uri, output.cv)
        self._write_optimization_outputs(job_posting_identifier, identifier, output)

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
        base_uri = f"job-postings/{job_posting_identifier}/cvs/{identifier}"
        for artifact in output.artifacts.values():
            self.repository.save_object(base_uri, artifact)

    def save_cv_optimization(
        self, job_posting_identifier: str, identifier: str, base_cv_identifier: str
    ):
        """
        Save a CV optimization to the repository.

        Args:
            job_posting_identifier: Identifier of the job posting
            identifier: Identifier for this optimization
            base_cv_identifier: Identifier of the base CV

        Returns:
            OptimizedCvRecord
        """
        base_uri = f"job-postings/{job_posting_identifier}/cvs/{identifier}"
        plan = self.repository.load_object(base_uri, CvTransformationPlan)
        cv = self.repository.get_optimized_cv(job_posting_identifier, identifier)

        if cv is None:
            raise ValueError(
                f"Cannot save CV optimization {identifier} for job posting {job_posting_identifier} — optimized CV is missing."
            )

        record = self.repository.add_optimized_cv(
            job_posting_identifier, identifier, base_cv_identifier, cv
        )

        if plan is not None:
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
            item["identifier"] for item in self.repository.list_job_postings(archived=False)
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
        base_uri = f"job-postings/{job_posting_identifier}/cvs/{identifier}"
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
            item["identifier"] for item in self.repository.list_job_postings(archived=False)
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

    def to_markdown(self, domain_object, record=None) -> str:
        return self.markdown_converter.convert(domain_object, record) or ""

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
