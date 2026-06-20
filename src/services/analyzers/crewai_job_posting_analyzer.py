import os
from models import JobPosting

os.environ["CREWAI_TRACING_ENABLED"] = "false"
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"


class CrewAiJobPostingAnalyzer:
    """CrewAI implementation of job posting analysis."""

    def analyze(self, url: str, content_file: str | None = None) -> JobPosting:
        from crews.job_posting_analysis.crew import JobPostingAnalysisCrew

        inputs = {
            "job_posting_url": url,
            "content_file": content_file,
        }

        crew = JobPostingAnalysisCrew()
        result = crew.crew().kickoff(inputs=inputs)

        if not isinstance(result.pydantic, JobPosting):
            raise TypeError("Expected JobPosting, got {}".format(type(result.pydantic)))

        return result.pydantic
