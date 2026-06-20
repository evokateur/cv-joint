from typing import Protocol
from models import CurriculumVitae, JobPosting
from .models import OptimizerOutput


class CvAnalysisPort(Protocol):
    """Implementation contract for CV analysis."""

    def analyze(self, file_path: str) -> CurriculumVitae:
        """Analyze a CV source file."""


class JobPostingAnalysisPort(Protocol):
    """Implementation contract for job posting analysis."""

    def analyze(self, url: str, content_file: str | None = None) -> JobPosting:
        """Analyze a job posting URL or local source file."""


class CvOptimizationPort(Protocol):
    """Implementation contract for CV optimization."""

    def optimize(self, cv: CurriculumVitae, job_posting: JobPosting) -> OptimizerOutput:
        """Optimize a CV for a job posting."""
