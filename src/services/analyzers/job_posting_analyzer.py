from models import JobPosting

from .ports import JobPostingAnalysisPort


class JobPostingAnalyzer:
    """
    Lightweight facade for extracting structured job posting data.
    """

    def __init__(self, implementation: JobPostingAnalysisPort | None = None):
        self._implementation = implementation

    def analyze(self, content_file: str, url: str) -> JobPosting:
        """
        Analyze a job posting from a local file and return structured JobPosting data.

        Args:
            content_file: Local file path to the job posting content
            url: Canonical posting URL, handed to the crew so it does not
                fabricate one for the required url field

        Returns:
            JobPosting Pydantic model with extracted data
        """
        return self._get_implementation().analyze(content_file, url)

    def _get_implementation(self) -> JobPostingAnalysisPort:
        if self._implementation is None:
            from .crewai_job_posting_analyzer import CrewAiJobPostingAnalyzer

            self._implementation = CrewAiJobPostingAnalyzer()
        return self._implementation
