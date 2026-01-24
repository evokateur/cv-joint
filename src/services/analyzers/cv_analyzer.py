import os
import tempfile

# Disable CrewAI tracing to prevent 20s timeout prompt
os.environ["CREWAI_TRACING_ENABLED"] = "false"

from crews.cv_analyzer.crew import CvAnalyzer as CvAnalyzerCrew
from models import CurriculumVitae


class CvAnalyzer:
    """
    Analyzer that wraps the CvAnalysis crew to extract structured CV data.

    This class abstracts the CrewAI implementation details from the service layer.
    """

    def analyze(self, file_path: str) -> CurriculumVitae:
        """
        Analyze a CV file and return structured CurriculumVitae data.

        Args:
            file_path: Path to CV file (JSON, YAML, or plain text)

        Returns:
            CurriculumVitae Pydantic model with extracted data
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            inputs = {
                "candidate_cv_path": file_path,
                "output_directory": temp_dir,
            }

            crew = CvAnalyzerCrew()
            result = crew.crew().kickoff(inputs=inputs)

            if not isinstance(result.pydantic, CurriculumVitae):
                raise TypeError(
                    "Expected CurriculumVitae, got {}".format(type(result.pydantic))
                )

            return result.pydantic
