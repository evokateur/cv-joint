import os

from models import CurriculumVitae, JobPosting

from .cv_optimizer import FileBasedCvOptimizer, OptimizerOutput


class CrewAiCvOptimizer(FileBasedCvOptimizer):
    """CrewAI implementation of CV optimization."""

    def optimize(self, cv: CurriculumVitae, job_posting: JobPosting) -> OptimizerOutput:
        os.environ["CREWAI_TRACING_ENABLED"] = "false"

        crew = self._build_crew()
        return self._optimize_with_files(
            cv,
            job_posting,
            lambda inputs: crew.crew().kickoff(inputs=inputs),
        )

    def _build_crew(self):
        from crews.cv_optimization.crew import CvOptimizationCrew

        return CvOptimizationCrew()
