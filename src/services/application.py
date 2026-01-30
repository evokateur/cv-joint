from typing import Any
from services.analyzers import JobPostingAnalyzer
from services.analyzers import CvAnalyzer
from repositories import FileSystemRepository


class ApplicationService:
    """
    Service layer for CV Joint operations.

    This class provides the application boundary between the UI and domain logic.
    All methods accept and return JSON-serializable dictionaries.
    """

    def __init__(self, repository: FileSystemRepository = None):
        self.job_posting_analyzer = JobPostingAnalyzer()
        self.cv_analyzer = CvAnalyzer()
        self.repository = repository or FileSystemRepository()

    def create_job_posting(
        self, url: str, content_file: str = None
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

    def save_job_posting(
        self, job_posting_data: dict[str, Any], identifier: str
    ) -> dict[str, Any]:
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
            Collection metadata dict
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

        metadata = self.repository.save_job_posting(job_posting, identifier)
        return metadata

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

    def save_cv(self, cv_data: dict[str, Any], identifier: str) -> dict[str, Any]:
        """
        Save a CV to the repository.

        Handles identifier collisions by appending a number suffix if the
        identifier already exists. This allows re-analyzing the same CV
        without overwriting the previous analysis.

        Args:
            cv_data: CV data dict (from create_cv)
            identifier: Identifier to use for this CV

        Returns:
            Collection metadata dict
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

        metadata = self.repository.save_cv(cv, identifier)
        return metadata

    def _generate_cv_identifier(self, name: str, profession: str) -> str:
        """Generate a URL-safe identifier from name and profession."""
        import re

        def slugify(text: str) -> str:
            text = text.lower()
            text = re.sub(r"[^\w\s-]", "", text)
            text = re.sub(r"[-\s]+", "-", text)
            return text.strip("-")

        return f"{slugify(name)}-{slugify(profession)}"

    def get_cvs(self) -> list[dict[str, Any]]:
        """
        Retrieve all saved CVs.

        Returns:
            list of CV metadata dictionaries
        """
        return self.repository.list_cvs()

    def create_optimization(self, job_posting_id: str, cv_id: str) -> dict[str, Any]:
        """
        Create a CV optimization for a job posting.

        Args:
            job_posting_id: Identifier of the job posting
            cv_id: Identifier of the base CV

        Returns:
            dict with optimization data including identifier
        """
        # TODO: Implement actual optimization workflow
        import datetime

        optimization_id = f"{job_posting_id}-{datetime.date.today()}"

        return {
            "identifier": optimization_id,
            "job_posting_id": job_posting_id,
            "cv_id": cv_id,
            "status": "completed",
            "files": {
                "transformation_plan": f"optimizations/{optimization_id}/cv_transformation_plan.json",
                "optimized_cv": f"optimizations/{optimization_id}/optimized_cv.json",
            },
        }

    def get_optimizations(self) -> list[dict[str, Any]]:
        """
        Retrieve all saved optimizations.

        Returns:
            list of optimization dictionaries
        """
        # TODO: Implement actual repository query
        return [
            {
                "identifier": "automattic-senior-engineer-2024-11-06",
                "job_posting": "Automattic - Senior Engineer",
                "cv": "Septimus Fall",
                "date": "2024-11-06",
            },
            {
                "identifier": "google-staff-swe-2024-11-05",
                "job_posting": "Google - Staff SWE",
                "cv": "Fritzi Ritz",
                "date": "2024-11-05",
            },
        ]

    def generate_pdf(self, optimization_id: str) -> dict[str, Any]:
        """
        Generate a PDF from an optimized CV.

        Args:
            optimization_id: Identifier of the optimization

        Returns:
            dict with PDF generation result
        """
        # TODO: Implement actual PDF generation
        return {
            "status": "success",
            "pdf_path": f"optimizations/{optimization_id}/optimized_cv.pdf",
        }
