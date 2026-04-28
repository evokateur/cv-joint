import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

os.environ["CREWAI_TRACING_ENABLED"] = "false"

from pydantic import BaseModel

from crews import CvOptimizationCrew
from models import CurriculumVitae, CvTransformationPlan, JobPosting

_OUTPUT_TYPES: dict[str, type[BaseModel]] = {
    "cv": CurriculumVitae,
    "transformation-plan": CvTransformationPlan,
}


@dataclass
class OptimizerOutput:
    cv: CurriculumVitae
    artifacts: dict[str, BaseModel] = field(default_factory=dict)


class CvOptimizer:
    """Facade over CvOptimizationCrew. Accepts domain objects, returns OptimizerOutput."""

    def optimize(self, cv: CurriculumVitae, job_posting: JobPosting) -> OptimizerOutput:
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

            crew = CvOptimizationCrew()
            crew.crew().kickoff(inputs=inputs)

            return self._load_output(output_dir)

    def _load_output(self, output_dir: Path) -> OptimizerOutput:
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
