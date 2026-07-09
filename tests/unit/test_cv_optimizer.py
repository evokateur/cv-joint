"""
Unit tests for CvOptimizer facade.
"""

import json
import pytest
from pathlib import Path

from models import CurriculumVitae, CvTransformationPlan, Contact, JobPosting
from services.analyzers.cv_optimizer import CvOptimizer, FileBasedCvOptimizer
from services.analyzers.models import OptimizerOutput


@pytest.fixture
def sample_cv():
    return CurriculumVitae(
        name="Jane Doe",
        profession="Software Engineer",
        contact=Contact(
            city="San Francisco",
            state="CA",
            email="jane@example.com",
            phone="555-1234",
            linkedin="linkedin.com/in/janedoe",
            github="github.com/janedoe",
        ),
        core_expertise=["Python"],
        qualifications=["10 years experience"],
        education=[],
        experience=[],
        additional_experience=[],
        areas_of_expertise=[],
        languages=[],
    )


@pytest.fixture
def sample_job_posting():
    return JobPosting(
        url="https://example.com/job/123",
        company="Acme Corp",
        title="Software Engineer",
        industry="Technology",
        description="Build great software",
        experience_level="Mid-level",
    )


@pytest.fixture
def sample_plan():
    return CvTransformationPlan(
        job_title="Software Engineer",
        company="Acme Corp",
        matching_skills=["Python"],
        missing_skills=[],
    )


def _fake_kickoff(inputs, cv, plan):
    """Simulates the crew writing output files to output_directory."""
    output_dir = Path(inputs["output_directory"])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "cv.json").write_text(json.dumps(cv.model_dump(mode="json")))
    (output_dir / "transformation-plan.json").write_text(
        json.dumps(plan.model_dump(mode="json"))
    )


class FakeKickoffOptimizer(FileBasedCvOptimizer):
    """Test double: drives FileBasedCvOptimizer with a provided kickoff callable."""

    def __init__(self, kickoff_fn):
        super().__init__()
        self._kickoff_fn = kickoff_fn

    def optimize(self, cv, job_posting):
        return self._optimize_with_files(cv, job_posting, self._kickoff_fn)


class TestCvOptimizerInterface:
    def test_optimize_returns_optimizer_output(
        self, sample_cv, sample_job_posting, sample_plan
    ):
        optimizer = CvOptimizer(implementation=FakeKickoffOptimizer(
            lambda inputs: _fake_kickoff(inputs, sample_cv, sample_plan)
        ))
        result = optimizer.optimize(sample_cv, sample_job_posting)

        assert isinstance(result, OptimizerOutput)

    def test_optimize_cv_is_curriculum_vitae(
        self, sample_cv, sample_job_posting, sample_plan
    ):
        optimizer = CvOptimizer(implementation=FakeKickoffOptimizer(
            lambda inputs: _fake_kickoff(inputs, sample_cv, sample_plan)
        ))
        result = optimizer.optimize(sample_cv, sample_job_posting)

        assert isinstance(result.cv, CurriculumVitae)
        assert result.cv.name == sample_cv.name

    def test_optimize_artifacts_contains_transformation_plan(
        self, sample_cv, sample_job_posting, sample_plan
    ):
        optimizer = CvOptimizer(implementation=FakeKickoffOptimizer(
            lambda inputs: _fake_kickoff(inputs, sample_cv, sample_plan)
        ))
        result = optimizer.optimize(sample_cv, sample_job_posting)

        assert "transformation-plan" in result.artifacts
        assert isinstance(result.artifacts["transformation-plan"], CvTransformationPlan)

    def test_optimize_passes_domain_objects_as_serialized_files(
        self, sample_cv, sample_job_posting, sample_plan
    ):
        captured_content = {}

        def capture_and_fake(inputs):
            captured_content["cv"] = json.loads(Path(inputs["cv_path"]).read_text())
            captured_content["job"] = json.loads(Path(inputs["job_posting_path"]).read_text())
            _fake_kickoff(inputs, sample_cv, sample_plan)

        optimizer = CvOptimizer(implementation=FakeKickoffOptimizer(capture_and_fake))
        optimizer.optimize(sample_cv, sample_job_posting)

        assert captured_content["cv"]["name"] == sample_cv.name
        assert captured_content["job"]["company"] == sample_job_posting.company

    def test_optimize_cleans_up_temp_directory(
        self, sample_cv, sample_job_posting, sample_plan
    ):
        captured = {}

        def capture_and_fake(inputs):
            captured.update(inputs)
            _fake_kickoff(inputs, sample_cv, sample_plan)

        optimizer = CvOptimizer(implementation=FakeKickoffOptimizer(capture_and_fake))
        optimizer.optimize(sample_cv, sample_job_posting)

        assert not Path(captured["output_directory"]).exists()
