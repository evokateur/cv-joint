import os
import tempfile

# Disable CrewAI tracing to prevent 20s timeout prompt
os.environ["CREWAI_TRACING_ENABLED"] = "false"

from crews import JobPostingAnalysisCrew
from models.schema import JobPosting


class JobPostingAnalyzer:
    """
    Analyzer that wraps the JobPostingAnalyzer crew to extract structured job posting data.

    This class abstracts the CrewAI implementation details from the service layer.
    """

    def analyze(self, url: str) -> JobPosting:
        """
        Analyze a job posting URL and return structured JobPosting data.

        Args:
            url: Job posting URL to analyze

        Returns:
            JobPosting Pydantic model with extracted data
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            inputs = {
                "job_posting_url": url,
                "output_directory": temp_dir,
            }

            crew = JobPostingAnalysisCrew()
            result = crew.crew().kickoff(inputs=inputs)

            if not isinstance(result.pydantic, JobPosting):
                raise TypeError(
                    "Expected JobPosting, got {}".format(type(result.pydantic))
                )

            return result.pydantic
