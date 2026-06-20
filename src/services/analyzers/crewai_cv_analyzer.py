import os

from models import CurriculumVitae


class CrewAiCvAnalyzer:
    """CrewAI implementation of CV analysis."""

    def analyze(self, file_path: str) -> CurriculumVitae:
        os.environ["CREWAI_TRACING_ENABLED"] = "false"

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
