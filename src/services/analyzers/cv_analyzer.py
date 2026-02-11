import os

os.environ["CREWAI_TRACING_ENABLED"] = "false"

from crews import CvAnalysisCrew
from models import CurriculumVitae


class CvAnalyzer:
    """
    Analyzer that wraps the CvAnalysis crew to extract structured CV data.
    """

    def analyze(self, file_path: str) -> CurriculumVitae:
        """
        Analyze a CV file and return structured CurriculumVitae data.

        Args:
            file_path: Path to CV file (JSON, YAML, or plain text)

        Returns:
            CurriculumVitae Pydantic model with extracted data
        """
        inputs = {
            "candidate_cv_path": file_path,
        }

        crew = CvAnalysisCrew()
        result = crew.crew().kickoff(inputs=inputs)

        if not isinstance(result.pydantic, CurriculumVitae):
            raise TypeError(
                "Expected CurriculumVitae, got {}".format(type(result.pydantic))
            )

        return result.pydantic
