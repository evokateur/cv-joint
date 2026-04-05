"""
Unit tests for filesystem repository.
"""

import pytest
import tempfile
from pathlib import Path

from repositories import FileSystemRepository
from models import JobPosting, CurriculumVitae


@pytest.fixture
def temp_data_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def repository(temp_data_dir):
    return FileSystemRepository(data_dir=temp_data_dir)


@pytest.fixture
def sample_job_posting():
    return JobPosting(
        url="https://example.com/job/123",
        company="Acme Corp",
        title="Software Engineer",
        industry="Technology",
        description="Build great software",
        experience_level="Mid-level",
        responsibilities=["Write code", "Review PRs"],
        technical_skills=["Python", "Testing"],
    )


@pytest.fixture
def sample_cv():
    from models import Contact

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
        summary_of_qualifications="10 years experience",
        education=[],
        experience=[],
        additional_experience=[],
        areas_of_expertise=[],
        languages=[],
    )


class TestFileSystemRepositoryInit:
    def test_creates_collections_directory(self, temp_data_dir):
        repo = FileSystemRepository(data_dir=temp_data_dir)
        assert (Path(temp_data_dir) / "collections").exists()

    def test_sets_data_dir(self, temp_data_dir):
        repo = FileSystemRepository(data_dir=temp_data_dir)
        assert repo.data_dir == Path(temp_data_dir)

    def test_expands_user_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = FileSystemRepository(data_dir=tmpdir)
            assert "~" not in str(repo.data_dir)


class TestJobPostingOperations:
    def test_add_and_get_job_posting(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "test-job")
        retrieved = repository.get_job_posting("test-job")

        assert retrieved is not None
        assert retrieved.company == "Acme Corp"
        assert retrieved.title == "Software Engineer"

    def test_list_job_postings(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "job-1")
        repository.add_job_posting(sample_job_posting, "job-2")

        listings = repository.list_job_postings()
        assert len(listings) == 2
        identifiers = [item["identifier"] for item in listings]
        assert "job-1" in identifiers
        assert "job-2" in identifiers

    def test_list_job_postings_empty(self, repository):
        listings = repository.list_job_postings()
        assert listings == []

    def test_remove_job_posting(self, repository, sample_job_posting, temp_data_dir):
        repository.add_job_posting(sample_job_posting, "to-delete")
        assert repository.remove_job_posting("to-delete") is True
        assert repository.get_job_posting("to-delete") is None
        assert not (Path(temp_data_dir) / "job-postings" / "to-delete").exists()

    def test_remove_job_posting_not_in_listing(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "to-delete")
        repository.remove_job_posting("to-delete")
        assert all(item["identifier"] != "to-delete" for item in repository.list_job_postings())

    def test_remove_nonexistent_job_posting(self, repository):
        assert repository.remove_job_posting("nonexistent") is False

    def test_remove_job_posting_cascades_to_optimization_plans(
        self, repository, sample_job_posting
    ):
        repository.add_job_posting(sample_job_posting, "to-delete")
        repository.add_cv_optimization("to-delete", "opt-1", "jane-doe")
        repository.add_cv_optimization("to-delete", "opt-2", "jane-doe")

        repository.remove_job_posting("to-delete")

        assert repository.list_cv_optimizations("to-delete") == []

    def test_remove_job_posting_cascades_to_cvs_collection(
        self, repository, sample_job_posting
    ):
        repository.add_job_posting(sample_job_posting, "to-delete")
        repository.add_cv_optimization("to-delete", "opt-1", "jane-doe")
        repository.add_cv_optimization("to-delete", "opt-2", "jane-doe")

        repository.remove_job_posting("to-delete")

        assert repository.get_cv_record("to-delete--opt-1") is None
        assert repository.get_cv_record("to-delete--opt-2") is None

    def test_add_job_posting_updates_existing(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "update-test")

        sample_job_posting.title = "Senior Software Engineer"
        repository.add_job_posting(sample_job_posting, "update-test")

        retrieved = repository.get_job_posting("update-test")
        assert retrieved.title == "Senior Software Engineer"

        listings = repository.list_job_postings()
        assert len(listings) == 1

    def test_job_posting_stored_in_correct_location(
        self, repository, sample_job_posting, temp_data_dir
    ):
        repository.add_job_posting(sample_job_posting, "location-test")
        expected_path = (
            Path(temp_data_dir) / "job-postings" / "location-test" / "job-posting.json"
        )
        assert expected_path.exists()

    def test_get_job_posting_record(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "test-job")
        record = repository.get_job_posting_record("test-job")

        assert record is not None
        assert record.identifier == "test-job"
        assert record.company == "Acme Corp"
        assert record.title == "Software Engineer"
        assert record.url == "https://example.com/job/123"
        assert record.experience_level == "Mid-level"
        assert record.created_at is not None

    def test_get_job_posting_record_not_found(self, repository):
        assert repository.get_job_posting_record("nonexistent") is None


class TestCvOperations:
    def test_add_and_get_cv(self, repository, sample_cv):
        repository.add_cv(sample_cv, "test-cv")
        retrieved = repository.get_cv("test-cv")

        assert retrieved is not None
        assert retrieved.name == "Jane Doe"
        assert retrieved.profession == "Software Engineer"

    def test_list_cvs(self, repository, sample_cv):
        repository.add_cv(sample_cv, "cv-1")
        repository.add_cv(sample_cv, "cv-2")

        listings = repository.list_cvs()
        assert len(listings) == 2
        identifiers = [item["identifier"] for item in listings]
        assert "cv-1" in identifiers
        assert "cv-2" in identifiers

    def test_list_cvs_empty(self, repository):
        listings = repository.list_cvs()
        assert listings == []

    def test_remove_cv(self, repository, sample_cv, temp_data_dir):
        repository.add_cv(sample_cv, "to-delete")
        assert repository.remove_cv("to-delete") is True
        assert repository.get_cv("to-delete") is None
        assert not (Path(temp_data_dir) / "cvs" / "to-delete").exists()

    def test_remove_cv_not_in_listing(self, repository, sample_cv):
        repository.add_cv(sample_cv, "to-delete")
        repository.remove_cv("to-delete")
        assert all(item["identifier"] != "to-delete" for item in repository.list_cvs())

    def test_remove_nonexistent_cv(self, repository):
        assert repository.remove_cv("nonexistent") is False

    def test_cv_stored_in_correct_location(self, repository, sample_cv, temp_data_dir):
        repository.add_cv(sample_cv, "location-test")
        expected_path = Path(temp_data_dir) / "cvs" / "location-test" / "cv.json"
        assert expected_path.exists()

    def test_get_cv_record(self, repository, sample_cv):
        repository.add_cv(sample_cv, "test-cv")
        record = repository.get_cv_record("test-cv")

        assert record is not None
        assert record.identifier == "test-cv"
        assert record.name == "Jane Doe"
        assert record.profession == "Software Engineer"
        assert record.created_at is not None

    def test_get_cv_record_not_found(self, repository):
        assert repository.get_cv_record("nonexistent") is None


class TestCvOptimizationOperations:
    @pytest.fixture
    def sample_plan(self):
        from models import CvTransformationPlan

        return CvTransformationPlan(
            job_title="Software Engineer",
            company="Acme Corp",
            matching_skills=["Python", "Testing"],
            missing_skills=["Kubernetes"],
            transferable_skills=["CI/CD experience"],
        )

    @pytest.fixture
    def repository_with_job_posting(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "acme-swe")
        return repository

    def _write_plan_file(self, temp_data_dir, job_posting_identifier, identifier, plan):
        """Helper to simulate crew writing transformation-plan.json."""
        import json

        plan_dir = (
            Path(temp_data_dir)
            / "job-postings"
            / job_posting_identifier
            / "cvs"
            / identifier
        )
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan_path = plan_dir / "transformation-plan.json"
        with open(plan_path, "w") as f:
            json.dump(plan.model_dump(mode="json"), f)

    def _write_cv_file(self, temp_data_dir, job_posting_identifier, identifier, cv):
        """Helper to simulate crew writing cv.json for an optimization."""
        import json

        cv_dir = (
            Path(temp_data_dir)
            / "job-postings"
            / job_posting_identifier
            / "cvs"
            / identifier
        )
        cv_dir.mkdir(parents=True, exist_ok=True)
        cv_path = cv_dir / "cv.json"
        with open(cv_path, "w") as f:
            json.dump(cv.model_dump(mode="json"), f)

    def test_add_and_get_cv_optimization_record(self, repository_with_job_posting):
        repository_with_job_posting.add_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="opt-123",
            base_cv_identifier="jane-doe-cv",
        )

        retrieved = repository_with_job_posting.get_cv_optimization_record(
            job_posting_identifier="acme-swe",
            identifier="opt-123",
        )
        assert retrieved is not None
        assert retrieved.identifier == "opt-123"
        assert retrieved.base_cv_identifier == "jane-doe-cv"

    def test_add_cv_optimization_creates_record(
        self, repository_with_job_posting, temp_data_dir
    ):
        import json

        repository_with_job_posting.add_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="opt-123",
            base_cv_identifier="jane-doe-cv",
        )
        collection_path = Path(temp_data_dir) / "collections" / "optimization-plans.json"
        assert collection_path.exists()
        with open(collection_path) as f:
            collection = json.load(f)
        assert any(
            item["identifier"] == "opt-123"
            and item["job_posting_identifier"] == "acme-swe"
            for item in collection
        )

    def test_add_cv_optimization_returns_record(self, repository_with_job_posting):
        record = repository_with_job_posting.add_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="opt-123",
            base_cv_identifier="jane-doe-cv",
        )
        assert record.identifier == "opt-123"
        assert record.base_cv_identifier == "jane-doe-cv"
        assert record.created_at is not None

    def test_add_cv_optimization_adds_cv_to_collection(
        self, repository_with_job_posting, sample_cv, temp_data_dir
    ):
        self._write_cv_file(temp_data_dir, "acme-swe", "opt-123", sample_cv)
        repository_with_job_posting.add_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="opt-123",
            base_cv_identifier="jane-doe-cv",
        )
        listings = repository_with_job_posting.list_cvs()
        compound_id = "acme-swe--opt-123"
        match = next((item for item in listings if item["identifier"] == compound_id), None)
        assert match is not None
        assert match["filepath"] == "job-postings/acme-swe/cvs/opt-123/cv.json"

    def test_get_cv_record_compound_identifier(self, repository_with_job_posting, sample_cv, temp_data_dir):
        self._write_cv_file(temp_data_dir, "acme-swe", "opt-123", sample_cv)
        repository_with_job_posting.add_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="opt-123",
            base_cv_identifier="jane-doe-cv",
        )
        record = repository_with_job_posting.get_cv_record("acme-swe--opt-123")
        assert record is not None
        assert record.identifier == "acme-swe--opt-123"
        assert record.filepath == "job-postings/acme-swe/cvs/opt-123/cv.json"

    def test_get_cv_compound_identifier(self, repository_with_job_posting, sample_cv, temp_data_dir):
        self._write_cv_file(temp_data_dir, "acme-swe", "opt-123", sample_cv)
        repository_with_job_posting.add_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="opt-123",
            base_cv_identifier="jane-doe-cv",
        )
        cv = repository_with_job_posting.get_cv("acme-swe--opt-123")
        assert cv is not None
        assert cv.name == sample_cv.name
        assert cv.profession == sample_cv.profession

    def test_get_cv_transformation_plan(
        self,
        repository_with_job_posting,
        sample_plan,
        temp_data_dir,
    ):
        self._write_plan_file(temp_data_dir, "acme-swe", "opt-123", sample_plan)
        repository_with_job_posting.add_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="opt-123",
            base_cv_identifier="jane-doe-cv",
        )

        retrieved = repository_with_job_posting.get_cv_transformation_plan(
            job_posting_identifier="acme-swe",
            optimization_identifier="opt-123",
        )
        assert retrieved is not None
        assert retrieved.job_title == "Software Engineer"
        assert retrieved.company == "Acme Corp"

    def test_list_cv_optimizations_for_job_posting(self, repository_with_job_posting):
        repository_with_job_posting.add_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="opt-1",
            base_cv_identifier="jane-doe-cv",
        )
        repository_with_job_posting.add_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="opt-2",
            base_cv_identifier="jane-doe-cv",
        )

        optimizations = repository_with_job_posting.list_cv_optimizations("acme-swe")
        assert len(optimizations) == 2
        identifiers = [opt["identifier"] for opt in optimizations]
        assert "opt-1" in identifiers
        assert "opt-2" in identifiers

    def test_list_cv_optimizations_returns_metadata_from_optimization_and_plan(
        self,
        repository_with_job_posting,
        sample_plan,
        temp_data_dir,
    ):
        self._write_plan_file(temp_data_dir, "acme-swe", "opt-123", sample_plan)
        repository_with_job_posting.add_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="opt-123",
            base_cv_identifier="jane-doe-cv",
        )

        optimizations = repository_with_job_posting.list_cv_optimizations("acme-swe")
        opt = optimizations[0]

        assert opt["identifier"] == "opt-123"
        assert opt["job_posting_identifier"] == "acme-swe"
        assert opt["base_cv_identifier"] == "jane-doe-cv"
        assert "created_at" in opt
        assert opt["job_title"] == "Software Engineer"
        assert opt["company"] == "Acme Corp"

    def test_list_cv_optimizations_reads_from_collection(
        self, repository_with_job_posting, sample_plan, temp_data_dir
    ):
        self._write_plan_file(temp_data_dir, "acme-swe", "opt-123", sample_plan)
        repository_with_job_posting.add_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="opt-123",
            base_cv_identifier="jane-doe-cv",
        )
        optimizations = repository_with_job_posting.list_cv_optimizations("acme-swe")
        assert len(optimizations) == 1
        assert optimizations[0]["identifier"] == "opt-123"

    def test_list_cv_optimizations_empty(self, repository_with_job_posting):
        optimizations = repository_with_job_posting.list_cv_optimizations("acme-swe")
        assert optimizations == []

    def test_list_cv_optimizations_ignores_directories_without_marker(
        self, repository_with_job_posting, sample_plan, temp_data_dir
    ):
        self._write_plan_file(temp_data_dir, "acme-swe", "orphaned", sample_plan)

        optimizations = repository_with_job_posting.list_cv_optimizations("acme-swe")
        assert optimizations == []

    def test_list_all_optimizations(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "job-1")
        repository.add_job_posting(sample_job_posting, "job-2")

        repository.add_cv_optimization(
            job_posting_identifier="job-1",
            identifier="opt-a",
            base_cv_identifier="jane-doe-cv",
        )
        repository.add_cv_optimization(
            job_posting_identifier="job-2",
            identifier="opt-b",
            base_cv_identifier="jane-doe-cv",
        )

        optimizations = repository.list_cv_optimizations()
        assert len(optimizations) == 2

        job_posting_ids = [opt["job_posting_identifier"] for opt in optimizations]
        assert "job-1" in job_posting_ids
        assert "job-2" in job_posting_ids

    def test_get_cv_optimization_record_not_found(self, repository_with_job_posting):
        result = repository_with_job_posting.get_cv_optimization_record(
            job_posting_identifier="acme-swe",
            identifier="nonexistent",
        )
        assert result is None

    def test_get_cv_transformation_plan_not_found(self, repository_with_job_posting):
        result = repository_with_job_posting.get_cv_transformation_plan(
            job_posting_identifier="acme-swe",
            optimization_identifier="nonexistent",
        )
        assert result is None

    def test_purge_cv_optimization(self, repository_with_job_posting, temp_data_dir):
        repository_with_job_posting.add_cv_optimization(
            identifier="opt-123",
            job_posting_identifier="acme-swe",
            base_cv_identifier="jane-doe-cv",
        )

        result = repository_with_job_posting.purge_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="opt-123",
        )
        assert result is True

        optimization_dir = (
            Path(temp_data_dir)
            / "job-postings"
            / "acme-swe"
            / "cvs"
            / "opt-123"
        )
        assert not optimization_dir.exists()

    def test_purge_cv_optimization_not_found(self, repository_with_job_posting):
        result = repository_with_job_posting.purge_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="nonexistent",
        )
        assert result is False

    def test_remove_cv_optimization(self, repository_with_job_posting, temp_data_dir):
        repository_with_job_posting.add_cv_optimization(
            identifier="opt-123",
            job_posting_identifier="acme-swe",
            base_cv_identifier="jane-doe-cv",
        )

        result = repository_with_job_posting.remove_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="opt-123",
        )
        assert result is True

        optimization_dir = (
            Path(temp_data_dir)
            / "job-postings"
            / "acme-swe"
            / "cvs"
            / "opt-123"
        )
        assert not optimization_dir.exists()
        assert repository_with_job_posting.get_cv_optimization_record("acme-swe", "opt-123") is None
        assert repository_with_job_posting.get_cv_record("acme-swe--opt-123") is None

    def test_remove_cv_optimization_not_found(self, repository_with_job_posting):
        result = repository_with_job_posting.remove_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="nonexistent",
        )
        assert result is False

    def test_remove_cv_optimization_requires_record(
        self, repository_with_job_posting, sample_plan, temp_data_dir
    ):
        self._write_plan_file(temp_data_dir, "acme-swe", "orphaned", sample_plan)

        result = repository_with_job_posting.remove_cv_optimization(
            job_posting_identifier="acme-swe",
            identifier="orphaned",
        )
        assert result is False


class TestListCvDataFiles:
    def _write_cv_file(self, temp_data_dir, job_posting_identifier, identifier, cv):
        import json

        cv_dir = (
            Path(temp_data_dir)
            / "job-postings"
            / job_posting_identifier
            / "cvs"
            / identifier
        )
        cv_dir.mkdir(parents=True, exist_ok=True)
        cv_path = cv_dir / "cv.json"
        with open(cv_path, "w") as f:
            json.dump(cv.model_dump(mode="json"), f)

    def test_includes_base_cvs(self, repository, sample_cv, temp_data_dir):
        repository.add_cv(sample_cv, "jane-doe")
        files = repository.list_cv_data_files()
        assert any(f["identifier"] == "jane-doe" for f in files)

    def test_uses_double_dash_separator_for_optimized_cvs(
        self, repository, sample_job_posting, sample_cv, temp_data_dir
    ):
        repository.add_job_posting(sample_job_posting, "acme-swe")
        self._write_cv_file(temp_data_dir, "acme-swe", "opt-123", sample_cv)
        repository.add_cv_optimization("acme-swe", "opt-123", "jane-doe")

        files = repository.list_cv_data_files()
        identifiers = [f["identifier"] for f in files]
        assert "acme-swe--opt-123" in identifiers
        assert "acme-swe-opt-123" not in identifiers

    def test_no_duplicates_for_optimized_cvs(
        self, repository, sample_job_posting, sample_cv, temp_data_dir
    ):
        repository.add_job_posting(sample_job_posting, "acme-swe")
        self._write_cv_file(temp_data_dir, "acme-swe", "opt-123", sample_cv)
        repository.add_cv_optimization("acme-swe", "opt-123", "jane-doe")

        files = repository.list_cv_data_files()
        compound_matches = [f for f in files if "opt-123" in f["identifier"]]
        assert len(compound_matches) == 1


class TestRenameJobPosting:
    def test_raises_when_not_found(self, repository):
        with pytest.raises(ValueError, match="not found"):
            repository.rename_job_posting("nonexistent", "new-id")

    def test_raises_on_collision(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "job-1")
        repository.add_job_posting(sample_job_posting, "job-2")
        with pytest.raises(ValueError, match="already exists"):
            repository.rename_job_posting("job-1", "job-2")

    def test_renames_directory(self, repository, sample_job_posting, temp_data_dir):
        repository.add_job_posting(sample_job_posting, "old-id")
        repository.rename_job_posting("old-id", "new-id")
        assert not (Path(temp_data_dir) / "job-postings" / "old-id").exists()
        assert (Path(temp_data_dir) / "job-postings" / "new-id").exists()

    def test_updates_collection(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "old-id")
        repository.rename_job_posting("old-id", "new-id")
        assert repository.get_job_posting_record("old-id") is None
        record = repository.get_job_posting_record("new-id")
        assert record is not None
        assert record.identifier == "new-id"

    def test_returns_new_record(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "old-id")
        record = repository.rename_job_posting("old-id", "new-id")
        assert record.identifier == "new-id"

    def test_preserves_created_at(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "old-id")
        original = repository.get_job_posting_record("old-id")
        record = repository.rename_job_posting("old-id", "new-id")
        assert record.created_at == original.created_at

    def test_repairs_job_posting_identifier_in_optimization_records(
        self, repository, sample_job_posting
    ):
        repository.add_job_posting(sample_job_posting, "old-id")
        repository.add_cv_optimization("old-id", "opt-1", "jane-doe")
        repository.add_cv_optimization("old-id", "opt-2", "jane-doe")

        repository.rename_job_posting("old-id", "new-id")

        opt1 = repository.get_cv_optimization_record("new-id", "opt-1")
        opt2 = repository.get_cv_optimization_record("new-id", "opt-2")
        assert opt1.job_posting_identifier == "new-id"
        assert opt2.job_posting_identifier == "new-id"
        assert repository.get_cv_record("new-id--opt-1") is not None
        assert repository.get_cv_record("new-id--opt-2") is not None
        assert repository.get_cv_record("old-id--opt-1") is None
        assert repository.get_cv_record("old-id--opt-2") is None


class TestRenameCv:
    def test_raises_when_not_found(self, repository):
        with pytest.raises(ValueError, match="not found"):
            repository.rename_cv("nonexistent", "new-id")

    def test_raises_on_collision(self, repository, sample_cv):
        repository.add_cv(sample_cv, "cv-1")
        repository.add_cv(sample_cv, "cv-2")
        with pytest.raises(ValueError, match="already exists"):
            repository.rename_cv("cv-1", "cv-2")

    def test_renames_directory(self, repository, sample_cv, temp_data_dir):
        repository.add_cv(sample_cv, "old-id")
        repository.rename_cv("old-id", "new-id")
        assert not (Path(temp_data_dir) / "cvs" / "old-id").exists()
        assert (Path(temp_data_dir) / "cvs" / "new-id").exists()

    def test_updates_collection(self, repository, sample_cv):
        repository.add_cv(sample_cv, "old-id")
        repository.rename_cv("old-id", "new-id")
        assert repository.get_cv_record("old-id") is None
        record = repository.get_cv_record("new-id")
        assert record is not None
        assert record.identifier == "new-id"

    def test_returns_new_record(self, repository, sample_cv):
        repository.add_cv(sample_cv, "old-id")
        record = repository.rename_cv("old-id", "new-id")
        assert record.identifier == "new-id"

    def test_repairs_base_cv_identifier_in_optimizations(
        self, repository, sample_job_posting, sample_cv
    ):
        repository.add_job_posting(sample_job_posting, "acme-swe")
        repository.add_cv(sample_cv, "old-cv")
        repository.add_cv_optimization("acme-swe", "opt-1", "old-cv")
        repository.add_cv_optimization("acme-swe", "opt-2", "old-cv")

        repository.rename_cv("old-cv", "new-cv")

        opt1 = repository.get_cv_optimization_record("acme-swe", "opt-1")
        opt2 = repository.get_cv_optimization_record("acme-swe", "opt-2")
        assert opt1.base_cv_identifier == "new-cv"
        assert opt2.base_cv_identifier == "new-cv"

    def test_does_not_repair_unrelated_optimizations(
        self, repository, sample_job_posting, sample_cv
    ):
        repository.add_job_posting(sample_job_posting, "acme-swe")
        repository.add_cv(sample_cv, "old-cv")
        repository.add_cv(sample_cv, "other-cv")
        repository.add_cv_optimization("acme-swe", "opt-1", "old-cv")
        repository.add_cv_optimization("acme-swe", "opt-2", "other-cv")

        repository.rename_cv("old-cv", "new-cv")

        opt2 = repository.get_cv_optimization_record("acme-swe", "opt-2")
        assert opt2.base_cv_identifier == "other-cv"


class TestRenameCvOptimization:
    def test_raises_when_not_found(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "acme-swe")
        with pytest.raises(ValueError, match="not found"):
            repository.rename_cv_optimization("acme-swe", "nonexistent", "new-id")

    def test_raises_on_collision(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "acme-swe")
        repository.add_cv_optimization("acme-swe", "opt-1", "jane-doe")
        repository.add_cv_optimization("acme-swe", "opt-2", "jane-doe")
        with pytest.raises(ValueError, match="already exists"):
            repository.rename_cv_optimization("acme-swe", "opt-1", "opt-2")

    def test_renames_directory(self, repository, sample_job_posting, temp_data_dir):
        repository.add_job_posting(sample_job_posting, "acme-swe")
        repository.add_cv_optimization("acme-swe", "old-id", "jane-doe")
        repository.rename_cv_optimization("acme-swe", "old-id", "new-id")
        assert not (
            Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "old-id"
        ).exists()
        assert (
            Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "new-id"
        ).exists()

    def test_updates_record_identifier(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "acme-swe")
        repository.add_cv_optimization("acme-swe", "old-id", "jane-doe")
        repository.rename_cv_optimization("acme-swe", "old-id", "new-id")
        assert repository.get_cv_optimization_record("acme-swe", "old-id") is None
        record = repository.get_cv_optimization_record("acme-swe", "new-id")
        assert record is not None
        assert record.identifier == "new-id"
        assert repository.get_cv_record("acme-swe--old-id") is None
        assert repository.get_cv_record("acme-swe--new-id") is not None

    def test_returns_new_record(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "acme-swe")
        repository.add_cv_optimization("acme-swe", "old-id", "jane-doe")
        record = repository.rename_cv_optimization("acme-swe", "old-id", "new-id")
        assert record.identifier == "new-id"
        assert record.base_cv_identifier == "jane-doe"
