from models import JobPosting

from .ports import JobPostingAnalysisPort


class JobPostingAnalyzer:
    """
    Lightweight facade for extracting structured job posting data.
    """

    def __init__(self, implementation: JobPostingAnalysisPort | None = None):
        self._implementation = implementation

    def analyze(self, url: str, content_file: str | None = None) -> JobPosting:
        """
        Analyze a job posting URL and return structured JobPosting data.

        Args:
            url: Job posting URL to analyze
            content_file: Optional local file path to use instead of fetching URL

        Returns:
            JobPosting Pydantic model with extracted data
        """
        return self._get_implementation().analyze(url, content_file)

    def _get_implementation(self) -> JobPostingAnalysisPort:
        if self._implementation is None:
            from .crewai_job_posting_analyzer import CrewAiJobPostingAnalyzer

            self._implementation = CrewAiJobPostingAnalyzer()
        return self._implementation
