import os
from models import CurriculumVitae

os.environ["CREWAI_TRACING_ENABLED"] = "false"
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"


class CrewAiCvAnalyzer:
    """CrewAI implementation of CV analysis."""

    def analyze(self, file_path: str) -> CurriculumVitae:
        from crews.cv_analysis.crew import CvAnalysisCrew

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
