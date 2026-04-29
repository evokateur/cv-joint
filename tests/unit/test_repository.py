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
        repository.upsert_job_posting(sample_job_posting, "test-job")
        retrieved = repository.get_job_posting("test-job")

        assert retrieved is not None
        assert retrieved.company == "Acme Corp"
        assert retrieved.title == "Software Engineer"

    def test_list_job_postings(self, repository, sample_job_posting):
        repository.upsert_job_posting(sample_job_posting, "job-1")
        repository.upsert_job_posting(sample_job_posting, "job-2")

        listings = repository.list_job_postings()
        assert len(listings) == 2
        identifiers = [item["identifier"] for item in listings]
        assert "job-1" in identifiers
        assert "job-2" in identifiers

    def test_list_job_postings_empty(self, repository):
        listings = repository.list_job_postings()
        assert listings == []

    def test_remove_job_posting(self, repository, sample_job_posting, temp_data_dir):
        repository.upsert_job_posting(sample_job_posting, "to-delete")
        assert repository.remove_job_posting("to-delete") is True
        assert repository.get_job_posting("to-delete") is None
        assert not (Path(temp_data_dir) / "job-postings" / "to-delete").exists()

    def test_remove_job_posting_not_in_listing(self, repository, sample_job_posting):
        repository.upsert_job_posting(sample_job_posting, "to-delete")
        repository.remove_job_posting("to-delete")
        assert all(item["identifier"] != "to-delete" for item in repository.list_job_postings())

    def test_remove_nonexistent_job_posting(self, repository):
        assert repository.remove_job_posting("nonexistent") is False

    def test_add_job_posting_updates_existing(self, repository, sample_job_posting):
        repository.upsert_job_posting(sample_job_posting, "update-test")

        sample_job_posting.title = "Senior Software Engineer"
        repository.upsert_job_posting(sample_job_posting, "update-test")

        retrieved = repository.get_job_posting("update-test")
        assert retrieved.title == "Senior Software Engineer"

        listings = repository.list_job_postings()
        assert len(listings) == 1

    def test_job_posting_stored_in_correct_location(
        self, repository, sample_job_posting, temp_data_dir
    ):
        repository.upsert_job_posting(sample_job_posting, "location-test")
        expected_path = (
            Path(temp_data_dir) / "job-postings" / "location-test" / "job-posting.json"
        )
        assert expected_path.exists()

    def test_get_job_posting_record(self, repository, sample_job_posting):
        repository.upsert_job_posting(sample_job_posting, "test-job")
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

    def test_list_job_postings_excludes_archived_by_default(
        self, repository, sample_job_posting
    ):
        repository.upsert_job_posting(sample_job_posting, "active-job")
        repository.upsert_job_posting(sample_job_posting, "archived-job")
        repository.archive_job_posting("archived-job")

        listings = repository.list_job_postings()
        identifiers = [item["identifier"] for item in listings]
        assert "active-job" in identifiers
        assert "archived-job" not in identifiers

    def test_list_job_postings_includes_archived_when_requested(
        self, repository, sample_job_posting
    ):
        repository.upsert_job_posting(sample_job_posting, "active-job")
        repository.upsert_job_posting(sample_job_posting, "archived-job")
        repository.archive_job_posting("archived-job")

        listings = repository.list_job_postings(archived=True)
        identifiers = [item["identifier"] for item in listings]
        assert "active-job" in identifiers
        assert "archived-job" in identifiers

    def test_archive_job_posting_sets_flag(self, repository, sample_job_posting):
        repository.upsert_job_posting(sample_job_posting, "test-job")
        record = repository.archive_job_posting("test-job")

        assert record.is_archived is True
        assert repository.get_job_posting_record("test-job").is_archived is True

    def test_mark_applied_sets_fields(self, repository, sample_job_posting):
        repository.upsert_job_posting(sample_job_posting, "test-job")
        record = repository.mark_applied("test-job", "my-cv")

        assert record.applied_with == "my-cv"
        assert record.applied_at is not None
        reloaded = repository.get_job_posting_record("test-job")
        assert reloaded.applied_with == "my-cv"
        assert reloaded.applied_at is not None

    def test_mark_applied_accepts_explicit_date(self, repository, sample_job_posting):
        from datetime import datetime

        date = datetime(2025, 1, 15)
        repository.upsert_job_posting(sample_job_posting, "test-job")
        record = repository.mark_applied("test-job", "my-cv", applied_at=date)

        assert record.applied_at == date
        assert repository.get_job_posting_record("test-job").applied_at == date


class TestCvOperations:
    def test_add_and_get_cv(self, repository, sample_cv):
        repository.upsert_cv(sample_cv, "test-cv")
        retrieved = repository.get_cv("test-cv")

        assert retrieved is not None
        assert retrieved.name == "Jane Doe"
        assert retrieved.profession == "Software Engineer"

    def test_list_cvs(self, repository, sample_cv):
        repository.upsert_cv(sample_cv, "cv-1")
        repository.upsert_cv(sample_cv, "cv-2")

        listings = repository.list_cvs()
        assert len(listings) == 2
        identifiers = [item["identifier"] for item in listings]
        assert "cv-1" in identifiers
        assert "cv-2" in identifiers

    def test_list_cvs_empty(self, repository):
        listings = repository.list_cvs()
        assert listings == []

    def test_remove_cv(self, repository, sample_cv, temp_data_dir):
        repository.upsert_cv(sample_cv, "to-delete")
        assert repository.remove_cv("to-delete") is True
        assert repository.get_cv("to-delete") is None
        assert not (Path(temp_data_dir) / "cvs" / "to-delete").exists()

    def test_remove_cv_not_in_listing(self, repository, sample_cv):
        repository.upsert_cv(sample_cv, "to-delete")
        repository.remove_cv("to-delete")
        assert all(item["identifier"] != "to-delete" for item in repository.list_cvs())

    def test_remove_nonexistent_cv(self, repository):
        assert repository.remove_cv("nonexistent") is False

    def test_cv_stored_in_correct_location(self, repository, sample_cv, temp_data_dir):
        repository.upsert_cv(sample_cv, "location-test")
        expected_path = Path(temp_data_dir) / "cvs" / "location-test" / "cv.json"
        assert expected_path.exists()

    def test_get_cv_record(self, repository, sample_cv):
        repository.upsert_cv(sample_cv, "test-cv")
        record = repository.get_cv_record("test-cv")

        assert record is not None
        assert record.identifier == "test-cv"
        assert record.name == "Jane Doe"
        assert record.profession == "Software Engineer"
        assert record.created_at is not None

    def test_get_cv_record_not_found(self, repository):
        assert repository.get_cv_record("nonexistent") is None


class TestRenameJobPosting:
    def test_raises_when_not_found(self, repository):
        with pytest.raises(ValueError, match="not found"):
            repository.rename_job_posting("nonexistent", "new-id")

    def test_raises_on_collision(self, repository, sample_job_posting):
        repository.upsert_job_posting(sample_job_posting, "job-1")
        repository.upsert_job_posting(sample_job_posting, "job-2")
        with pytest.raises(ValueError, match="already exists"):
            repository.rename_job_posting("job-1", "job-2")

    def test_renames_directory(self, repository, sample_job_posting, temp_data_dir):
        repository.upsert_job_posting(sample_job_posting, "old-id")
        repository.rename_job_posting("old-id", "new-id")
        assert not (Path(temp_data_dir) / "job-postings" / "old-id").exists()
        assert (Path(temp_data_dir) / "job-postings" / "new-id").exists()

    def test_updates_collection(self, repository, sample_job_posting):
        repository.upsert_job_posting(sample_job_posting, "old-id")
        repository.rename_job_posting("old-id", "new-id")
        assert repository.get_job_posting_record("old-id") is None
        record = repository.get_job_posting_record("new-id")
        assert record is not None
        assert record.identifier == "new-id"

    def test_returns_new_record(self, repository, sample_job_posting):
        repository.upsert_job_posting(sample_job_posting, "old-id")
        record = repository.rename_job_posting("old-id", "new-id")
        assert record.identifier == "new-id"

    def test_preserves_created_at(self, repository, sample_job_posting):
        repository.upsert_job_posting(sample_job_posting, "old-id")
        original = repository.get_job_posting_record("old-id")
        record = repository.rename_job_posting("old-id", "new-id")
        assert record.created_at == original.created_at



class TestRenameCv:
    def test_raises_when_not_found(self, repository):
        with pytest.raises(ValueError, match="not found"):
            repository.rename_cv("nonexistent", "new-id")

    def test_raises_on_collision(self, repository, sample_cv):
        repository.upsert_cv(sample_cv, "cv-1")
        repository.upsert_cv(sample_cv, "cv-2")
        with pytest.raises(ValueError, match="already exists"):
            repository.rename_cv("cv-1", "cv-2")

    def test_renames_directory(self, repository, sample_cv, temp_data_dir):
        repository.upsert_cv(sample_cv, "old-id")
        repository.rename_cv("old-id", "new-id")
        assert not (Path(temp_data_dir) / "cvs" / "old-id").exists()
        assert (Path(temp_data_dir) / "cvs" / "new-id").exists()

    def test_updates_collection(self, repository, sample_cv):
        repository.upsert_cv(sample_cv, "old-id")
        repository.rename_cv("old-id", "new-id")
        assert repository.get_cv_record("old-id") is None
        record = repository.get_cv_record("new-id")
        assert record is not None
        assert record.identifier == "new-id"

    def test_returns_new_record(self, repository, sample_cv):
        repository.upsert_cv(sample_cv, "old-id")
        record = repository.rename_cv("old-id", "new-id")
        assert record.identifier == "new-id"



class TestOptimizedCvRecord:
    def test_constructs_with_required_fields(self):
        from models import OptimizedCvRecord
        from datetime import datetime

        record = OptimizedCvRecord(
            identifier="opt-1",
            job_posting_identifier="acme-swe",
            base_cv_identifier="jane-doe",
            name="Jane Doe",
            profession="Software Engineer",
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        )
        assert record.identifier == "opt-1"
        assert record.name == "Jane Doe"
        assert record.profession == "Software Engineer"

    def test_has_no_transformation_plan_filepath(self):
        from models import OptimizedCvRecord
        assert not hasattr(OptimizedCvRecord.model_fields, "transformation_plan_filepath")

    def test_optional_job_title_and_company(self):
        from models import OptimizedCvRecord
        from datetime import datetime

        record = OptimizedCvRecord(
            identifier="opt-1",
            job_posting_identifier="acme-swe",
            base_cv_identifier="jane-doe",
            name="Jane Doe",
            profession="Software Engineer",
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        )
        assert record.job_title is None
        assert record.company is None


# ---------------------------------------------------------------------------
# New tests for step 3 cascade/cleanup behavior
# ---------------------------------------------------------------------------

class TestRemoveJobPostingCascadesOptimizedCvs:
    def test_cascades_to_optimized_cvs_collection(self, repository, sample_job_posting, sample_cv):
        repository.upsert_job_posting(sample_job_posting, "to-delete")
        repository.upsert_optimized_cv("to-delete", "opt-1", "jane-doe", sample_cv)
        repository.upsert_optimized_cv("to-delete", "opt-2", "jane-doe", sample_cv)
        repository.remove_job_posting("to-delete")
        assert repository.list_optimized_cvs("to-delete") == []


class TestRenameJobPostingOptimizedCvs:
    def test_repairs_job_posting_identifier_in_optimized_cvs(
        self, repository, sample_job_posting, sample_cv
    ):
        repository.upsert_job_posting(sample_job_posting, "old-id")
        repository.upsert_optimized_cv("old-id", "opt-1", "jane-doe", sample_cv)
        repository.upsert_optimized_cv("old-id", "opt-2", "jane-doe", sample_cv)
        repository.rename_job_posting("old-id", "new-id")
        assert repository.get_optimized_cv_record("old-id", "opt-1") is None
        assert repository.get_optimized_cv_record("new-id", "opt-1") is not None
        assert repository.get_optimized_cv_record("new-id", "opt-1").job_posting_identifier == "new-id"
        assert repository.get_optimized_cv_record("new-id", "opt-2").job_posting_identifier == "new-id"


class TestRenameCvOptimizedCvs:
    def test_repairs_base_cv_identifier_in_optimized_cvs(
        self, repository, sample_job_posting, sample_cv
    ):
        repository.upsert_job_posting(sample_job_posting, "acme-swe")
        repository.upsert_cv(sample_cv, "old-cv")
        repository.upsert_optimized_cv("acme-swe", "opt-1", "old-cv", sample_cv)
        repository.upsert_optimized_cv("acme-swe", "opt-2", "old-cv", sample_cv)
        repository.rename_cv("old-cv", "new-cv")
        assert repository.get_optimized_cv_record("acme-swe", "opt-1").base_cv_identifier == "new-cv"
        assert repository.get_optimized_cv_record("acme-swe", "opt-2").base_cv_identifier == "new-cv"

    def test_does_not_repair_unrelated_optimizations(
        self, repository, sample_job_posting, sample_cv
    ):
        repository.upsert_job_posting(sample_job_posting, "acme-swe")
        repository.upsert_cv(sample_cv, "old-cv")
        repository.upsert_cv(sample_cv, "other-cv")
        repository.upsert_optimized_cv("acme-swe", "opt-1", "old-cv", sample_cv)
        repository.upsert_optimized_cv("acme-swe", "opt-2", "other-cv", sample_cv)
        repository.rename_cv("old-cv", "new-cv")
        assert repository.get_optimized_cv_record("acme-swe", "opt-2").base_cv_identifier == "other-cv"


class TestListCvsBaseOnly:
    def test_list_cvs_returns_only_base_cvs(
        self, repository, sample_job_posting, sample_cv
    ):
        repository.upsert_cv(sample_cv, "jane-doe")
        repository.upsert_job_posting(sample_job_posting, "acme-swe")
        repository.upsert_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
        listings = repository.list_cvs()
        assert len(listings) == 1
        assert listings[0]["identifier"] == "jane-doe"
