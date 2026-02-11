import tempfile
from pathlib import Path
from typing import Any, Optional

from config.settings import get_markdown_root_dir
from config.settings import get_data_dir
from services.analyzers import JobPostingAnalyzer
from services.analyzers import CvAnalyzer
from services.analyzers import CvOptimizer
from .converters import MarkdownConverter
from .exporters import MarkdownExporter
from repositories import FileSystemRepository
from infrastructure import MarkdownWriter
from renderers.latex import render_latex, latex_to_pdf


class ApplicationService:
    """
    Application service for CV Joint operations.
    """

    def __init__(
        self,
        repository: Optional[FileSystemRepository] = None,
        markdown_writer: Optional[MarkdownWriter] = None,
    ):
        self.job_posting_analyzer = JobPostingAnalyzer()
        self.cv_analyzer = CvAnalyzer()
        self.cv_optimizer = CvOptimizer()
        self.repository = repository or FileSystemRepository(data_dir=get_data_dir())
        self.markdown_converter = MarkdownConverter()
        markdown_writer = markdown_writer or MarkdownWriter(
            root_dir=get_markdown_root_dir()
        )
        self.markdown_exporter = MarkdownExporter(
            self.repository, markdown_writer, self.markdown_converter
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

    def get_job_posting(self, identifier: str):
        """Retrieve a job posting by identifier."""
        return self.repository.get_job_posting(identifier)

    def get_job_postings(self) -> list[dict[str, Any]]:
        """
        Retrieve all saved job postings.

        Returns:
            list of job posting metadata dictionaries
        """
        return self.repository.list_job_postings()

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
        identifier = self._generate_cv_identifier(cv.name, cv.profession)
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

    def _generate_cv_identifier(self, name: str, profession: str) -> str:
        """Generate a URL-safe identifier from name and profession."""
        import re

        def slugify(text: str) -> str:
            text = text.lower()
            text = re.sub(r"[^\w\s-]", "", text)
            text = re.sub(r"[-\s]+", "-", text)
            return text.strip("-")

        return f"{slugify(name)}-{slugify(profession)}"

    def get_cv(self, identifier: str):
        """Retrieve a CV by identifier."""
        return self.repository.get_cv(identifier)

    def get_cvs(self) -> list[dict[str, Any]]:
        """
        Retrieve all saved CVs.

        Returns:
            list of CV metadata dictionaries
        """
        return self.repository.list_cvs()

    def regenerate_markdown(self, collection_name: Optional[str] = None) -> int:
        """
        Regenerate all markdown files from stored domain objects.

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

        cv_path = str(self.repository.get_absolute_path("cvs", cv_identifier))

        job_posting_path = str(
            self.repository.get_absolute_path("job-postings", job_posting_identifier)
        )

        identifier = f"{datetime.date.today()}"
        output_directory = str(
            self.repository.get_cv_optimization_dir(job_posting_identifier, identifier)
        )

        self.cv_optimizer.optimize(
            cv_path,
            job_posting_path,
            output_directory,
        )

        plan = self.repository.get_cv_transformation_plan(
            job_posting_identifier, identifier
        )
        cv = self.repository.get_optimized_cv(job_posting_identifier, identifier)

        identifiers = {
            "job_posting_identifier": job_posting_identifier,
            "identifier": identifier,
            "base_cv_identifier": cv_identifier,
        }

        return (
            plan.model_dump() if plan else {},
            cv.model_dump() if cv else {},
            identifiers,
        )

    def get_cv_transformation_plan(
        self, job_posting_identifier: str, optimization_identifier: str
    ):
        """
        Retrieve the CV transformation plan for a CV optimization.
        """
        return self.repository.get_cv_transformation_plan(
            job_posting_identifier, optimization_identifier
        )

    def save_cv_optimization(
        self, job_posting_identifier: str, identifier: str, base_cv_identifier: str
    ):
        """
        Save a CV optimization to the repository

        Args:
            job_posting_identifier: Identifier of the job posting
            identifier: Identifier for this optimization
            base_cv_identifier: Identifier of the base CV

        Returns:
            CvOptimizationRecord
        """

        plan = self.repository.get_cv_transformation_plan(
            job_posting_identifier, identifier
        )

        cv = self.repository.get_optimized_cv(job_posting_identifier, identifier)

        if plan is None or cv is None:
            raise ValueError(
                f"Cannot save CV optimization {identifier} for job posting {job_posting_identifier}  because the transformation plan or optimized CV is missing."
            )

        record = self.repository.add_cv_optimization(
            job_posting_identifier, identifier, base_cv_identifier
        )

        self.markdown_exporter.export_cv_transformation_plan(record, plan)
        self.markdown_exporter.export_cv(record, cv)

        return record

    def get_cv_optimizations(self) -> list[dict[str, Any]]:
        """
        Retrieve all saved cv optimizations.

        Returns:
            list of optimization metadata dictionaries
        """
        return self.repository.list_cv_optimizations()

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
        plan = self.repository.get_cv_transformation_plan(
            job_posting_identifier, identifier
        )
        cv = self.repository.get_optimized_cv(job_posting_identifier, identifier)

        return (
            plan.model_dump() if plan else {},
            cv.model_dump() if cv else {},
        )

    def purge_cv_optimization(
        self, job_posting_identifier: str, identifier: str
    ) -> bool:
        """
        Delete an unsaved CV optimization from disk.

        Args:
            job_posting_identifier: Identifier of the job posting
            identifier: Identifier of the optimization

        Returns:
            True if deleted, False if not found
        """
        return self.repository.purge_cv_optimization(job_posting_identifier, identifier)

    def get_cv_data_filepaths(self) -> list[dict[str, Any]]:
        return self.repository.list_cv_data_files()

    def get_cv_template_names(self) -> list[str]:
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent
        templates_dir = project_root / "templates"
        return [str(p.name) for p in templates_dir.glob("*cv*.tex")]

    def to_markdown(self, domain_object) -> str:
        return self.markdown_converter.convert(domain_object)

    def generate_pdf_file(self, data_path: str, template_name: str) -> str:
        tmp_dir = tempfile.mkdtemp()
        tex_path = str(Path(tmp_dir) / "output.tex")
        render_latex(data_path, tex_path, template_name)
        return latex_to_pdf(tex_path)
