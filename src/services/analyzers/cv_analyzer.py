from models import CurriculumVitae

from .ports import CvAnalysisPort


class CvAnalyzer:
    """
    Lightweight facade for extracting structured CV data.
    """

    def __init__(self, implementation: CvAnalysisPort | None = None):
        self._implementation = implementation

    def analyze(self, file_path: str) -> CurriculumVitae:
        """
        Analyze a CV file and return structured CurriculumVitae data.

        Args:
            file_path: Path to CV file (JSON, YAML, or plain text)

        Returns:
            CurriculumVitae Pydantic model with extracted data
        """
        return self._get_implementation().analyze(file_path)

    def _get_implementation(self) -> CvAnalysisPort:
        if self._implementation is None:
            from .crewai_cv_analyzer import CrewAiCvAnalyzer

            self._implementation = CrewAiCvAnalyzer()
        return self._implementation
