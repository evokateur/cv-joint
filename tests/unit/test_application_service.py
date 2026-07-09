"""
Unit tests for application service markdown generation.
"""

import json
import shutil
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from repositories import FileSystemRepository
from services import ApplicationService
from models import JobPosting, CurriculumVitae, Contact, CvTransformationPlan


@pytest.fixture
def temp_data_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def service(temp_data_dir):
    repository = FileSystemRepository(data_dir=temp_data_dir)
    return ApplicationService(repository=repository)


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
        qualifications=["10 years experience"],
        education=[],
        experience=[],
        additional_experience=[],
        areas_of_expertise=[],
        languages=[],
    ).model_dump()


class TestFindJobPostingByUrl:
    def test_returns_record_when_url_exists(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "acme-job")
        record = service.find_job_posting_by_url("https://example.com/job/123")
        assert record is not None
        assert record.identifier == "acme-job"

    def test_returns_none_when_url_not_found(self, service):
        assert service.find_job_posting_by_url("https://example.com/nope") is None


class TestCreateJobPostingDuplicateUrl:
    def test_raises_when_url_already_analyzed(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "acme-job")

        from unittest.mock import MagicMock
        from models import JobPosting

        service.job_posting_analyzer = MagicMock()
        service.job_posting_analyzer.analyze.return_value = JobPosting(**sample_job_posting_data)

        with pytest.raises(ValueError, match="already analyzed: acme-job"):
            service.create_job_posting("https://example.com/job/123")


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
        md_path = Path(temp_data_dir) / "cvs" / "test-cv" / "curriculum-vitae.md"
        assert md_path.exists()
        content = md_path.read_text()
        assert "# Jane Doe" in content


class TestExportMarkdown:
    def test_export_all(
        self, service, sample_job_posting_data, sample_cv_data, temp_data_dir
    ):
        service.save_job_posting(sample_job_posting_data, "job-1")
        service.save_cv(sample_cv_data, "cv-1")

        job_md = Path(temp_data_dir) / "job-postings" / "job-1" / "job-posting.md"
        cv_md = Path(temp_data_dir) / "cvs" / "cv-1" / "curriculum-vitae.md"
        job_md.unlink()
        cv_md.unlink()

        count = service.export_markdown()
        assert count == 2
        assert job_md.exists()
        assert cv_md.exists()

    def test_export_by_collection(
        self, service, sample_job_posting_data, sample_cv_data, temp_data_dir
    ):
        service.save_job_posting(sample_job_posting_data, "job-1")
        service.save_cv(sample_cv_data, "cv-1")

        job_md = Path(temp_data_dir) / "job-postings" / "job-1" / "job-posting.md"
        cv_md = Path(temp_data_dir) / "cvs" / "cv-1" / "curriculum-vitae.md"
        job_md.unlink()
        cv_md.unlink()

        count = service.export_markdown(collection_name="job-postings")
        assert count == 1
        assert job_md.exists()
        assert not cv_md.exists()

    def test_export_optimizations(
        self, service, sample_job_posting_data, sample_cv_data, temp_data_dir
    ):
        service.save_job_posting(sample_job_posting_data, "job-1")
        service.save_cv(sample_cv_data, "cv-1")

        plan = CvTransformationPlan(job_title="Software Engineer", company="Acme Corp")
        cv = CurriculumVitae(**sample_cv_data)
        base_uri = "job-postings/job-1/cvs/opt-1"
        service.repository.add_optimized_cv("job-1", "opt-1", "cv-1", cv)
        service.repository.save_object(base_uri, plan)

        opt_dir = Path(temp_data_dir) / "job-postings" / "job-1" / "cvs" / "opt-1"
        plan_md = opt_dir / "cv-transformation-plan.md"
        cv_md = opt_dir / "curriculum-vitae.md"

        count = service.export_markdown(collection_name="optimizations")
        assert count == 2
        assert plan_md.exists()
        assert cv_md.exists()

    def test_export_cvs_excludes_optimized(
        self, service, sample_job_posting_data, sample_cv_data
    ):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.save_cv(sample_cv_data, "jane-doe")
        service.repository.add_optimized_cv(
            "acme-swe", "opt-1", "jane-doe", CurriculumVitae(**sample_cv_data)
        )

        count = service.export_markdown(collection_name="cvs")
        assert count == 1

    def test_unknown_collection_raises(self, service):
        with pytest.raises(ValueError, match="Unknown collection: invalid"):
            service.export_markdown(collection_name="invalid")


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
        md_path = Path(temp_data_dir) / "cvs" / "jane-doe" / "curriculum-vitae.md"
        assert md_path.exists()
        service.remove_cv("jane-doe")
        assert not md_path.exists()


class TestRegenerateJobPosting:
    def test_raises_when_not_found(self, service):
        with pytest.raises(ValueError, match="Job posting not found"):
            service.reanalyze_job_posting("nonexistent")

    def test_creates_new_record_with_suffix(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        updated = JobPosting(**{**sample_job_posting_data, "title": "Senior Engineer"})
        service._analyze_job_posting_url = MagicMock(return_value=updated)

        new_record = service.reanalyze_job_posting("acme-swe")

        assert new_record.identifier == "acme-swe-2"
        assert service.get_job_posting("acme-swe").title == sample_job_posting_data["title"]
        assert service.get_job_posting("acme-swe-2").title == "Senior Engineer"

    def test_reanalyze_of_suffixed_identifier_increments_base(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.save_job_posting(sample_job_posting_data, "acme-swe-2")
        service._analyze_job_posting_url = MagicMock(
            return_value=JobPosting(**sample_job_posting_data)
        )

        new_record = service.reanalyze_job_posting("acme-swe-2")

        assert new_record.identifier == "acme-swe-3"

    def test_regenerates_markdown(self, service, sample_job_posting_data, temp_data_dir):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service._analyze_job_posting_url = MagicMock(
            return_value=JobPosting(**sample_job_posting_data)
        )

        service.reanalyze_job_posting("acme-swe")

        md_path = Path(temp_data_dir) / "job-postings" / "acme-swe-2" / "job-posting.md"
        assert md_path.exists()


class TestRegenerateCv:
    def test_raises_when_not_found(self, service):
        with pytest.raises(ValueError, match="CV not found"):
            service.reanalyze_cv("nonexistent", "/some/file.yaml")

    def test_creates_new_record_with_suffix(self, service, sample_cv_data):
        service.save_cv(sample_cv_data, "jane-doe")
        updated = CurriculumVitae(**{**sample_cv_data, "profession": "Senior Engineer"})
        service.cv_analyzer = MagicMock()
        service.cv_analyzer.analyze.return_value = updated

        new_record = service.reanalyze_cv("jane-doe", "/some/file.yaml")

        assert new_record.identifier == "jane-doe-2"
        assert service.get_cv("jane-doe").profession == sample_cv_data["profession"]
        assert service.get_cv("jane-doe-2").profession == "Senior Engineer"

    def test_reanalyze_of_suffixed_identifier_increments_base(self, service, sample_cv_data):
        service.save_cv(sample_cv_data, "jane-doe")
        service.save_cv(sample_cv_data, "jane-doe-2")
        service.cv_analyzer = MagicMock()
        service.cv_analyzer.analyze.return_value = CurriculumVitae(**sample_cv_data)

        new_record = service.reanalyze_cv("jane-doe-2", "/some/file.yaml")

        assert new_record.identifier == "jane-doe-3"

    def test_regenerates_markdown(self, service, sample_cv_data, temp_data_dir):
        service.save_cv(sample_cv_data, "jane-doe")
        service.cv_analyzer = MagicMock()
        service.cv_analyzer.analyze.return_value = CurriculumVitae(**sample_cv_data)

        service.reanalyze_cv("jane-doe", "/some/file.yaml")

        md_path = Path(temp_data_dir) / "cvs" / "jane-doe-2" / "curriculum-vitae.md"
        assert md_path.exists()


class TestRegenerateCvOptimization:
    @pytest.fixture
    def service_with_optimization(self, service, sample_job_posting_data, sample_cv_data):
        from services.analyzers.models import OptimizerOutput

        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.save_cv(sample_cv_data, "jane-doe")

        plan = CvTransformationPlan(
            job_title="Software Engineer",
            company="Acme Corp",
            matching_skills=["Python"],
            missing_skills=[],
            transferable_skills=[],
        )
        cv = CurriculumVitae(**sample_cv_data)

        service.repository.add_optimized_cv("acme-swe", "opt-1", "jane-doe", cv)

        service.cv_optimizer = MagicMock()
        service.cv_optimizer.optimize.return_value = OptimizerOutput(
            cv=cv,
            artifacts={"transformation-plan": plan},
        )
        return service

    def test_raises_when_not_found(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        with pytest.raises(ValueError, match="CV optimization not found"):
            service.reanalyze_cv_optimization("acme-swe", "nonexistent")

    def test_creates_new_record_with_suffix(self, service_with_optimization):
        new_record = service_with_optimization.reanalyze_cv_optimization("acme-swe", "opt-1")
        assert new_record.identifier == "opt-1-2"
        assert service_with_optimization.repository.get_optimized_cv_record("acme-swe", "opt-1") is not None
        assert new_record.base_cv_identifier == "jane-doe"

    def test_reanalyze_of_suffixed_identifier_increments_base(self, service_with_optimization):
        service_with_optimization.reanalyze_cv_optimization("acme-swe", "opt-1")
        new_record = service_with_optimization.reanalyze_cv_optimization("acme-swe", "opt-1-2")
        assert new_record.identifier == "opt-1-3"

    def test_regenerates_markdown(self, service_with_optimization, temp_data_dir):
        service_with_optimization.reanalyze_cv_optimization("acme-swe", "opt-1")
        cv_md = Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "opt-1-2" / "curriculum-vitae.md"
        plan_md = Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "opt-1-2" / "cv-transformation-plan.md"
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
        assert (Path(temp_data_dir) / "cvs" / "new-id" / "curriculum-vitae.md").exists()

    def test_repairs_optimization_references(
        self, service, sample_job_posting_data, sample_cv_data
    ):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.save_cv(sample_cv_data, "old-cv")
        service.repository.add_optimized_cv("acme-swe", "opt-1", "old-cv", CurriculumVitae(**sample_cv_data))
        service.rename_cv("old-cv", "new-cv")
        record = service.repository.get_optimized_cv_record("acme-swe", "opt-1")
        assert record.base_cv_identifier == "new-cv"


class TestGetJobPostings:
    def test_forwards_location_param(self):
        mock_repo = MagicMock()
        mock_repo.list_job_postings.return_value = []
        service = ApplicationService(repository=mock_repo)
        service.get_job_postings(location="archived")
        mock_repo.list_job_postings.assert_called_once_with(location="archived", all=False)

    def test_forwards_all_param(self):
        mock_repo = MagicMock()
        mock_repo.list_job_postings.return_value = []
        service = ApplicationService(repository=mock_repo)
        service.get_job_postings(all=True)
        mock_repo.list_job_postings.assert_called_once_with(location=None, all=True)


class TestArchiveJobPosting:
    def test_delegates_to_repository(self):
        mock_repo = MagicMock()
        service = ApplicationService(repository=mock_repo)
        service.markdown_exporter = MagicMock()
        service.archive_job_posting("acme-swe")
        mock_repo.archive_job_posting.assert_called_once_with("acme-swe")

    def test_does_not_call_exporter(self):
        mock_repo = MagicMock()
        mock_exporter = MagicMock()
        service = ApplicationService(repository=mock_repo)
        service.markdown_exporter = mock_exporter
        service.archive_job_posting("acme-swe")
        mock_exporter.export_job_posting.assert_not_called()


class TestMarkApplied:
    def test_delegates_to_repository(self):
        mock_repo = MagicMock()
        service = ApplicationService(repository=mock_repo)
        service.markdown_exporter = MagicMock()
        service.mark_applied("acme-swe", "my-cv")
        mock_repo.mark_applied.assert_called_once_with("acme-swe", "my-cv", applied_at=None)

    def test_forwards_applied_at(self):
        from datetime import datetime
        mock_repo = MagicMock()
        service = ApplicationService(repository=mock_repo)
        service.markdown_exporter = MagicMock()
        date = datetime(2025, 1, 15)
        service.mark_applied("acme-swe", "my-cv", applied_at=date)
        mock_repo.mark_applied.assert_called_once_with("acme-swe", "my-cv", applied_at=date)

    def test_does_not_call_exporter(self):
        mock_repo = MagicMock()
        mock_exporter = MagicMock()
        service = ApplicationService(repository=mock_repo)
        service.markdown_exporter = mock_exporter
        service.mark_applied("acme-swe", "my-cv")
        mock_exporter.export_job_posting.assert_not_called()


# ---------------------------------------------------------------------------
# New tests for step 3 service method updates
# ---------------------------------------------------------------------------

class TestGetCvOptimizationsNew:
    def test_excludes_optimizations_from_archived_job_postings(
        self, service, sample_job_posting_data, sample_cv_data
    ):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.save_cv(sample_cv_data, "jane-doe")
        service.repository.add_optimized_cv("acme-swe", "opt-1", "jane-doe", CurriculumVitae(**sample_cv_data))
        service.archive_job_posting("acme-swe")
        opts = service.get_cv_optimizations()
        assert not any(o.get("job_posting_identifier") == "acme-swe" for o in opts)

    def test_includes_optimizations_from_active_job_postings(
        self, service, sample_job_posting_data, sample_cv_data
    ):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.save_cv(sample_cv_data, "jane-doe")
        service.repository.add_optimized_cv("acme-swe", "opt-1", "jane-doe", CurriculumVitae(**sample_cv_data))
        opts = service.get_cv_optimizations()
        assert any(o.get("job_posting_identifier") == "acme-swe" for o in opts)


class TestRemoveCvOptimizationNew:
    def test_returns_true_when_found(self, service, sample_job_posting_data, sample_cv_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.repository.add_optimized_cv("acme-swe", "opt-1", "jane-doe", CurriculumVitae(**sample_cv_data))
        assert service.remove_cv_optimization("acme-swe", "opt-1") is True

    def test_returns_false_when_not_found(self, service, sample_job_posting_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        assert service.remove_cv_optimization("acme-swe", "nonexistent") is False

    def test_removes_from_repository(self, service, sample_job_posting_data, sample_cv_data):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.repository.add_optimized_cv("acme-swe", "opt-1", "jane-doe", CurriculumVitae(**sample_cv_data))
        service.remove_cv_optimization("acme-swe", "opt-1")
        assert service.repository.get_optimized_cv_record("acme-swe", "opt-1") is None


class TestRenameCvOptimizationNew:
    def test_data_accessible_at_new_identifier(
        self, service, sample_job_posting_data, sample_cv_data
    ):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.repository.add_optimized_cv("acme-swe", "opt-1", "jane-doe", CurriculumVitae(**sample_cv_data))
        service.rename_cv_optimization("acme-swe", "opt-1", "new-id")
        assert service.repository.get_optimized_cv_record("acme-swe", "opt-1") is None
        assert service.repository.get_optimized_cv_record("acme-swe", "new-id") is not None


class TestPurgeCvOptimization:
    def test_deletes_directory_without_removing_record(
        self, service, sample_job_posting_data, sample_cv_data, temp_data_dir
    ):
        from pathlib import Path
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        service.repository.add_optimized_cv("acme-swe", "opt-1", "jane-doe", CurriculumVitae(**sample_cv_data))
        service.purge_cv_optimization("acme-swe", "opt-1")
        opt_dir = Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "opt-1"
        assert not opt_dir.exists()
        assert service.repository.get_optimized_cv_record("acme-swe", "opt-1") is not None


# ---------------------------------------------------------------------------
# CJ-17 regression tests: service and exporter must use parent stored path
# ---------------------------------------------------------------------------

def _move_job_posting(repository, identifier, new_rel):
    collection = repository._load_collection(repository.job_postings_collection)
    item = next(i for i in collection if i["identifier"] == identifier)
    old_abs = repository.data_dir / item["path"]
    new_abs = repository.data_dir / new_rel
    new_abs.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old_abs), str(new_abs))
    item["path"] = new_rel
    repository._save_collection(repository.job_postings_collection, collection)


class TestSaveCvOptimizationUsesParentPath:
    """save_cv_optimization must write to the parent's stored path and export markdown."""

    def test_saves_to_parent_stored_path(
        self, service, sample_job_posting_data, sample_cv_data, temp_data_dir
    ):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        _move_job_posting(service.repository, "acme-swe", "job-postings/archived/acme-swe")

        cv = CurriculumVitae(**sample_cv_data)
        plan = CvTransformationPlan(job_title="Software Engineer", company="Acme Corp")

        service.markdown_exporter = MagicMock()
        service.save_cv_optimization("acme-swe", "opt-1", "jane-doe", cv, plan)

        service.markdown_exporter.export_cv_transformation_plan.assert_called_once()


class TestExportOptimizationsUsesParentPath:
    """export('optimizations') must load artifacts and write markdown via the parent's stored path."""

    def test_finds_artifacts_after_parent_path_moved(
        self, service, sample_job_posting_data, sample_cv_data, temp_data_dir
    ):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        cv = CurriculumVitae(**sample_cv_data)
        plan = CvTransformationPlan(job_title="Software Engineer", company="Acme Corp")

        service.repository.add_optimized_cv("acme-swe", "opt-1", "jane-doe", cv)

        cv_dir = Path(temp_data_dir) / "job-postings/acme-swe/cvs/opt-1"
        plan_data = plan.model_dump(mode="json")
        plan_data["_type"] = "CvTransformationPlan"
        (cv_dir / "cv-transformation-plan.json").write_text(json.dumps(plan_data))

        # Moving the parent carries the nested cvs/ subdir with it.
        _move_job_posting(service.repository, "acme-swe", "job-postings/archived/acme-swe")

        count = service.export_markdown(collection_name="optimizations")

        # CV via export_cv counts as 1; plan via load_all_objects counts as 1 more.
        assert count == 2

    def test_markdown_written_at_parent_stored_path(
        self, service, sample_job_posting_data, sample_cv_data, temp_data_dir
    ):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        cv = CurriculumVitae(**sample_cv_data)
        service.repository.add_optimized_cv("acme-swe", "opt-1", "jane-doe", cv)

        _move_job_posting(service.repository, "acme-swe", "job-postings/archived/acme-swe")

        service.export_markdown(collection_name="optimizations")

        cv_md = Path(temp_data_dir) / "job-postings/archived/acme-swe/cvs/opt-1/curriculum-vitae.md"
        assert cv_md.exists()


class TestGetCvOptimizationUsesParentPath:
    """get_cv_optimization must load the transformation plan from the parent's stored path."""

    def test_finds_plan_at_parent_stored_path(
        self, service, sample_job_posting_data, sample_cv_data, temp_data_dir
    ):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        _move_job_posting(service.repository, "acme-swe", "job-postings/archived/acme-swe")

        cv = CurriculumVitae(**sample_cv_data)
        plan = CvTransformationPlan(job_title="Software Engineer", company="Acme Corp")

        service.repository.add_optimized_cv("acme-swe", "opt-1", "jane-doe", cv)

        cv_dir = Path(temp_data_dir) / "job-postings/archived/acme-swe/cvs/opt-1"
        plan_json = plan.model_dump(mode="json")
        plan_json["_type"] = "CvTransformationPlan"
        (cv_dir / "cv-transformation-plan.json").write_text(json.dumps(plan_json))

        plan_data, _ = service.get_cv_optimization("acme-swe", "opt-1")

        assert plan_data != {}


class TestCreateJobPostingFromUrl:
    def test_analyzes_fetched_url_when_no_content_file(self, service, sample_job_posting_data):
        service._analyze_job_posting_url = MagicMock(
            return_value=JobPosting(**sample_job_posting_data)
        )

        service.create_job_posting(url="https://example.com/job/new")

        service._analyze_job_posting_url.assert_called_once_with("https://example.com/job/new")

    def test_url_injected_over_analyzer_value(self, service, sample_job_posting_data):
        service._analyze_job_posting_url = MagicMock(
            return_value=JobPosting(**{**sample_job_posting_data, "url": "Not specified"})
        )

        data, _ = service.create_job_posting(url="https://example.com/job/new")

        assert data["url"] == "https://example.com/job/new"

    def test_uses_content_file_when_provided(self, service, sample_job_posting_data, tmp_path):
        content = tmp_path / "job.md"
        content.write_text("# Job")
        service._analyze_job_posting_url = MagicMock()
        service.job_posting_analyzer = MagicMock()
        service.job_posting_analyzer.analyze.return_value = JobPosting(**sample_job_posting_data)

        service.create_job_posting(url="https://example.com/job/123", content_file=str(content))

        service._analyze_job_posting_url.assert_not_called()
        service.job_posting_analyzer.analyze.assert_called_once_with(str(content))


class TestCreateCv:
    def test_analyzes_content_file(self, service, sample_cv_data, tmp_path):
        content = tmp_path / "cv.yaml"
        content.write_text("name: Jane")
        service.cv_analyzer = MagicMock()
        service.cv_analyzer.analyze.return_value = MagicMock(**sample_cv_data)

        service.create_cv(content_file=str(content))

        service.cv_analyzer.analyze.assert_called_once_with(str(content))

    def test_raises_when_content_file_missing(self, service):
        with pytest.raises(ValueError, match="content_file must be provided"):
            service.create_cv()


class TestAddDocument:
    def test_bare_object_uri_uses_source_filename(self, service, sample_job_posting_data, tmp_path):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        source = tmp_path / "notes.md"
        source.write_text("# Notes")
        doc_uri = service.add_document("job-postings/acme-swe", str(source))
        assert doc_uri == "job-postings/acme-swe/notes.md"

    def test_full_document_uri_uses_given_name(self, service, sample_job_posting_data, tmp_path):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        source = tmp_path / "notes.md"
        source.write_text("# Notes")
        doc_uri = service.add_document("job-postings/acme-swe/intake.md", str(source))
        assert doc_uri == "job-postings/acme-swe/intake.md"

    def test_content_written_to_directory(self, service, sample_job_posting_data, tmp_path, temp_data_dir):
        service.save_job_posting(sample_job_posting_data, "acme-swe")
        source = tmp_path / "notes.md"
        source.write_text("# Notes")
        service.add_document("job-postings/acme-swe", str(source))
        dest = Path(temp_data_dir) / "job-postings" / "acme-swe" / "notes.md"
        assert dest.exists()
        assert dest.read_text() == "# Notes"

    def test_object_not_found_raises(self, service, tmp_path):
        source = tmp_path / "notes.md"
        source.write_text("# Notes")
        with pytest.raises(ValueError, match="Not found"):
            service.add_document("job-postings/nonexistent", str(source))
