"""
Unit tests for application service markdown generation.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from repositories import FileSystemRepository
from infrastructure import MarkdownWriter
from services import ApplicationService
from models import JobPosting, CurriculumVitae, Contact, CvTransformationPlan


@pytest.fixture
def temp_data_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def service(temp_data_dir):
    repository = FileSystemRepository(data_dir=temp_data_dir)
    markdown_writer = MarkdownWriter(root_dir=temp_data_dir)
    return ApplicationService(repository=repository, markdown_writer=markdown_writer)


@pytest.fixture
def sample_job_posting_data():
    return JobPosting(
        url="https://example.com/job/123",
        company="Acme Corp",
        title="Software Engineer",
        industry="Technology",
        description="Build great software",
        experience_level="Mid-level",
        responsibilities=["Write code", "Review PRs"],
        technical_skills=["Python", "Testing"],
    ).model_dump()


@pytest.fixture
def sample_cv_data():
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
        core_expertise=["Python", "Testing"],
        summary_of_qualifications=["10 years experience"],
        education=[],
        experience=[],
        additional_experience=[],
        areas_of_expertise=[],
        languages=[],
    ).model_dump()


class TestSaveJobPostingMarkdown:
    def test_creates_markdown(self, service, sample_job_posting_data, temp_data_dir):
        service.save_job_posting(sample_job_posting_data, "test-job")
        md_path = Path(temp_data_dir) / "job-postings" / "test-job" / "job-posting.md"
        assert md_path.exists()
        content = md_path.read_text()
        assert "Software Engineer at Acme Corp" in content

    def test_not_specified_company_omitted_from_title(self, service, temp_data_dir):
        data = JobPosting(
            url="https://example.com/job/456",
            company="Not specified",
            title="Developer",
            industry="Tech",
            description="A job",
            experience_level="Senior",
        ).model_dump()

        service.save_job_posting(data, "no-company")
        md_path = Path(temp_data_dir) / "job-postings" / "no-company" / "job-posting.md"
        content = md_path.read_text()
        assert "# Developer\n" in content
        assert "at Not specified" not in content


class TestSaveCvMarkdown:
    def test_creates_markdown(self, service, sample_cv_data, temp_data_dir):
        service.save_cv(sample_cv_data, "test-cv")
        md_path = Path(temp_data_dir) / "cvs" / "test-cv" / "cv.md"
        assert md_path.exists()
        content = md_path.read_text()
        assert "# Jane Doe" in content


class TestRegenerateMarkdown:
    def test_regenerate_all(
        self, service, sample_job_posting_data, sample_cv_data, temp_data_dir
    ):
        service.save_job_posting(sample_job_posting_data, "job-1")
        service.save_cv(sample_cv_data, "cv-1")

        job_md = Path(temp_data_dir) / "job-postings" / "job-1" / "job-posting.md"
        cv_md = Path(temp_data_dir) / "cvs" / "cv-1" / "cv.md"
        job_md.unlink()
        cv_md.unlink()

        count = service.regenerate_markdown()
        assert count == 2
        assert job_md.exists()
        assert cv_md.exists()

    def test_regenerate_by_collection(
        self, service, sample_job_posting_data, sample_cv_data, temp_data_dir
    ):
        service.save_job_posting(sample_job_posting_data, "job-1")
        service.save_cv(sample_cv_data, "cv-1")

        job_md = Path(temp_data_dir) / "job-postings" / "job-1" / "job-posting.md"
        cv_md = Path(temp_data_dir) / "cvs" / "cv-1" / "cv.md"
        job_md.unlink()
        cv_md.unlink()

        count = service.regenerate_markdown(collection_name="job-postings")
        assert count == 1
        assert job_md.exists()
        assert not cv_md.exists()

    def test_unknown_collection_raises(self, service):
        with pytest.raises(ValueError, match="Unknown collection: invalid"):
            service.regenerate_markdown(collection_name="invalid")


class TestRemoveJobPosting:
    def test_returns_true_when_found(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        assert service.remove_job_posting("acme-swe") is True

    def test_returns_false_when_not_found(self, service):
        assert service.remove_job_posting("nonexistent") is False

    def test_removes_from_repository(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.remove_job_posting("acme-swe")
        assert service.get_job_posting("acme-swe") is None

    def test_deletes_markdown(self, service, sample_job_posting_data, temp_data_dir):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        md_path = Path(temp_data_dir) / "job-postings" / "acme-swe" / "job-posting.md"
        assert md_path.exists()
        service.remove_job_posting("acme-swe")
        assert not md_path.exists()


class TestRemoveCv:
    def test_returns_true_when_found(self, service, sample_cv_data):
        service.save_cv(sample_cv_data, "jane-doe")
        assert service.remove_cv("jane-doe") is True

    def test_returns_false_when_not_found(self, service):
        assert service.remove_cv("nonexistent") is False

    def test_removes_from_repository(self, service, sample_cv_data):
        service.save_cv(sample_cv_data, "jane-doe")
        service.remove_cv("jane-doe")
        assert service.get_cv("jane-doe") is None

    def test_deletes_markdown(self, service, sample_cv_data, temp_data_dir):
        service.save_cv(sample_cv_data, "jane-doe")
        md_path = Path(temp_data_dir) / "cvs" / "jane-doe" / "cv.md"
        assert md_path.exists()
        service.remove_cv("jane-doe")
        assert not md_path.exists()


class TestRemoveCvOptimization:
    def test_returns_true_when_found(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.repository.add_cv_optimization("acme-swe", "opt-1", "jane-doe")
        assert service.remove_cv_optimization("acme-swe", "opt-1") is True

    def test_returns_false_when_not_found(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        assert service.remove_cv_optimization("acme-swe", "nonexistent") is False

    def test_removes_from_repository(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.repository.add_cv_optimization("acme-swe", "opt-1", "jane-doe")
        service.remove_cv_optimization("acme-swe", "opt-1")
        assert service.repository.get_cv_optimization_record("acme-swe", "opt-1") is None


class TestRegenerateJobPosting:
    def test_raises_when_not_found(self, service):
        with pytest.raises(ValueError, match="Job posting not found"):
            service.regenerate_job_posting("nonexistent")

    def test_overwrites_record(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        updated = JobPosting(**{**sample_job_posting_data, "title": "Senior Engineer"})
        service.job_posting_analyzer = MagicMock()
        service.job_posting_analyzer.analyze.return_value = updated

        service.regenerate_job_posting("acme-swe")

        retrieved = service.get_job_posting("acme-swe")
        assert retrieved.title == "Senior Engineer"

    def test_regenerates_markdown(self, service, sample_job_posting_data, temp_data_dir):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        md_path = Path(temp_data_dir) / "job-postings" / "acme-swe" / "job-posting.md"
        md_path.unlink()
        service.job_posting_analyzer = MagicMock()
        service.job_posting_analyzer.analyze.return_value = JobPosting(**sample_job_posting_data)

        service.regenerate_job_posting("acme-swe")

        assert md_path.exists()


class TestRegenerateCv:
    def test_raises_when_not_found(self, service):
        with pytest.raises(ValueError, match="CV not found"):
            service.regenerate_cv("nonexistent", "/some/file.yaml")

    def test_overwrites_record(self, service, sample_cv_data):
        service.save_cv(sample_cv_data, "jane-doe")
        updated = CurriculumVitae(**{**sample_cv_data, "profession": "Senior Engineer"})
        service.cv_analyzer = MagicMock()
        service.cv_analyzer.analyze.return_value = updated

        service.regenerate_cv("jane-doe", "/some/file.yaml")

        retrieved = service.get_cv("jane-doe")
        assert retrieved.profession == "Senior Engineer"

    def test_regenerates_markdown(self, service, sample_cv_data, temp_data_dir):
        service.save_cv(sample_cv_data, "jane-doe")
        md_path = Path(temp_data_dir) / "cvs" / "jane-doe" / "cv.md"
        md_path.unlink()
        service.cv_analyzer = MagicMock()
        service.cv_analyzer.analyze.return_value = CurriculumVitae(**sample_cv_data)

        service.regenerate_cv("jane-doe", "/some/file.yaml")

        assert md_path.exists()


class TestRegenerateCvOptimization:
    @pytest.fixture
    def service_with_optimization(self, service, sample_job_posting_data, sample_cv_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.save_cv(sample_cv_data, "jane-doe")
        service.repository.add_cv_optimization("acme-swe", "opt-1", "jane-doe")

        plan = CvTransformationPlan(
            job_title="Software Engineer",
            company="Acme Corp",
            matching_skills=["Python"],
            missing_skills=[],
            transferable_skills=[],
        )
        cv = CurriculumVitae(**sample_cv_data)

        def fake_optimize(_cv_path, _job_path, output_dir):
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            with open(Path(output_dir) / "transformation-plan.json", "w") as f:
                json.dump(plan.model_dump(mode="json"), f)
            with open(Path(output_dir) / "cv.json", "w") as f:
                json.dump(cv.model_dump(mode="json"), f)

        service.cv_optimizer = MagicMock()
        service.cv_optimizer.optimize.side_effect = fake_optimize
        return service

    def test_raises_when_not_found(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        with pytest.raises(ValueError, match="CV optimization not found"):
            service.regenerate_cv_optimization("acme-swe", "nonexistent")

    def test_overwrites_record(self, service_with_optimization):
        service_with_optimization.regenerate_cv_optimization("acme-swe", "opt-1")
        record = service_with_optimization.repository.get_cv_optimization_record("acme-swe", "opt-1")
        assert record is not None
        assert record.base_cv_identifier == "jane-doe"

    def test_regenerates_markdown(self, service_with_optimization, temp_data_dir):
        service_with_optimization.regenerate_cv_optimization("acme-swe", "opt-1")
        cv_md = Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "opt-1" / "cv.md"
        plan_md = Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "opt-1" / "transformation-plan.md"
        assert cv_md.exists()
        assert plan_md.exists()


class TestRenameJobPosting:
    def test_raises_when_not_found(self, service):
        with pytest.raises(ValueError, match="not found"):
            service.rename_job_posting("nonexistent", "new-id")

    def test_raises_on_collision(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "job-1")
        service.save_job_posting(sample_job_posting_data, "job-2")
        with pytest.raises(ValueError, match="already exists"):
            service.rename_job_posting("job-1", "job-2")

    def test_data_accessible_at_new_identifier(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "old-id")
        service.rename_job_posting("old-id", "new-id")
        assert service.get_job_posting("old-id") is None
        assert service.get_job_posting("new-id") is not None

    def test_moves_markdown(self, service, sample_job_posting_data, temp_data_dir):
        service.save_job_posting(sample_job_posting_data, "old-id")
        service.rename_job_posting("old-id", "new-id")
        assert not (Path(temp_data_dir) / "job-postings" / "old-id").exists()
        assert (Path(temp_data_dir) / "job-postings" / "new-id" / "job-posting.md").exists()


class TestRenameCv:
    def test_raises_when_not_found(self, service):
        with pytest.raises(ValueError, match="not found"):
            service.rename_cv("nonexistent", "new-id")

    def test_raises_on_collision(self, service, sample_cv_data):
        service.save_cv(sample_cv_data, "cv-1")
        service.save_cv(sample_cv_data, "cv-2")
        with pytest.raises(ValueError, match="already exists"):
            service.rename_cv("cv-1", "cv-2")

    def test_data_accessible_at_new_identifier(self, service, sample_cv_data):
        service.save_cv(sample_cv_data, "old-id")
        service.rename_cv("old-id", "new-id")
        assert service.get_cv("old-id") is None
        assert service.get_cv("new-id") is not None

    def test_moves_markdown(self, service, sample_cv_data, temp_data_dir):
        service.save_cv(sample_cv_data, "old-id")
        service.rename_cv("old-id", "new-id")
        assert not (Path(temp_data_dir) / "cvs" / "old-id").exists()
        assert (Path(temp_data_dir) / "cvs" / "new-id" / "cv.md").exists()

    def test_repairs_optimization_references(
        self, service, sample_job_posting_data, sample_cv_data
    ):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.save_cv(sample_cv_data, "old-cv")
        service.repository.add_cv_optimization("acme-swe", "opt-1", "old-cv")
        service.rename_cv("old-cv", "new-cv")
        record = service.repository.get_cv_optimization_record("acme-swe", "opt-1")
        assert record.base_cv_identifier == "new-cv"


class TestRenameCvOptimization:
    def test_raises_when_not_found(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        with pytest.raises(ValueError, match="not found"):
            service.rename_cv_optimization("acme-swe", "nonexistent", "new-id")

    def test_raises_on_collision(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.repository.add_cv_optimization("acme-swe", "opt-1", "jane-doe")
        service.repository.add_cv_optimization("acme-swe", "opt-2", "jane-doe")
        with pytest.raises(ValueError, match="already exists"):
            service.rename_cv_optimization("acme-swe", "opt-1", "opt-2")

    def test_data_accessible_at_new_identifier(
        self, service, sample_job_posting_data
    ):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.repository.add_cv_optimization("acme-swe", "opt-1", "jane-doe")
        service.rename_cv_optimization("acme-swe", "opt-1", "new-id")
        assert service.repository.get_cv_optimization_record("acme-swe", "opt-1") is None
        assert service.repository.get_cv_optimization_record("acme-swe", "new-id") is not None

    def test_moves_markdown(self, service, sample_job_posting_data, temp_data_dir):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.repository.add_cv_optimization("acme-swe", "opt-1", "jane-doe")
        opt_dir = Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs"
        (opt_dir / "opt-1").mkdir(parents=True, exist_ok=True)
        (opt_dir / "opt-1" / "cv.md").write_text("# CV")
        service.rename_cv_optimization("acme-swe", "opt-1", "new-id")
        assert not (opt_dir / "opt-1").exists()
        assert (opt_dir / "new-id" / "cv.md").exists()
