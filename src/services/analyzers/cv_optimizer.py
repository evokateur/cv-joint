import json
import tempfile
from pathlib import Path

from pydantic import BaseModel

from models import CurriculumVitae, CvTransformationPlan, JobPosting
from .ports import CvOptimizationPort, OptimizerOutput

_OUTPUT_TYPES: dict[str, type[BaseModel]] = {
    "cv": CurriculumVitae,
    "transformation-plan": CvTransformationPlan,
}


class CvOptimizer:
    """Lightweight facade for CV optimization."""

    def __init__(self, implementation: CvOptimizationPort | None = None):
        self._implementation = implementation

    def optimize(self, cv: CurriculumVitae, job_posting: JobPosting) -> OptimizerOutput:
        return self._get_implementation().optimize(cv, job_posting)

    def _get_implementation(self) -> CvOptimizationPort:
        if self._implementation is None:
            from .crewai_cv_optimizer import CrewAiCvOptimizer

            self._implementation = CrewAiCvOptimizer()
        return self._implementation


class OutputLoader:
    """Loads optimizer artifacts written by an implementation."""

    def load(self, output_dir: Path) -> OptimizerOutput:
        optimized_cv = None
        artifacts: dict[str, BaseModel] = {}

        for json_file in output_dir.glob("*.json"):
            stem = json_file.stem
            model_class = _OUTPUT_TYPES.get(stem)
            if model_class is None:
                continue
            data = json.loads(json_file.read_text())
            obj = model_class(**data)
            if stem == "cv" and isinstance(obj, CurriculumVitae):
                optimized_cv = obj
            else:
                artifacts[stem] = obj

        if optimized_cv is None:
            raise ValueError("Crew did not produce a cv.json output")

        return OptimizerOutput(cv=optimized_cv, artifacts=artifacts)


class FileBasedCvOptimizer:
    """Base helper for optimizer implementations that exchange JSON files."""

    def __init__(self, output_loader: OutputLoader | None = None):
        self._output_loader = output_loader or OutputLoader()

    def _optimize_with_files(
        self,
        cv: CurriculumVitae,
        job_posting: JobPosting,
        kickoff,
    ) -> OptimizerOutput:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "input"
            output_dir = Path(temp_dir) / "output"
            input_dir.mkdir()
            output_dir.mkdir()

            cv_path = input_dir / "cv.json"
            cv_path.write_text(cv.model_dump_json())

            job_posting_path = input_dir / "job-posting.json"
            job_posting_path.write_text(job_posting.model_dump_json())

            inputs = {
                "cv_path": str(cv_path),
                "job_posting_path": str(job_posting_path),
                "output_directory": str(output_dir),
            }

            kickoff(inputs)

            return self._output_loader.load(output_dir)
