from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel

from models import CurriculumVitae, JobPosting


@dataclass
class OptimizerOutput:
    cv: CurriculumVitae
    artifacts: dict[str, BaseModel] = field(default_factory=dict)


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

    def optimize(
        self, cv: CurriculumVitae, job_posting: JobPosting
    ) -> OptimizerOutput:
        """Optimize a CV for a job posting."""
