import os
from models import CurriculumVitae, JobPosting
from .cv_optimizer import FileBasedCvOptimizer
from .models import OptimizerOutput

os.environ["CREWAI_TRACING_ENABLED"] = "false"


class CrewAiCvOptimizer(FileBasedCvOptimizer):
    """CrewAI implementation of CV optimization."""

    def optimize(self, cv: CurriculumVitae, job_posting: JobPosting) -> OptimizerOutput:
        from crews.cv_optimization.crew import CvOptimizationCrew

        crew = CvOptimizationCrew()
        return self._optimize_with_files(
            cv,
            job_posting,
            lambda inputs: crew.crew().kickoff(inputs=inputs),
        )
