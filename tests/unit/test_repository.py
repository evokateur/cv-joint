"""
Unit tests for filesystem repository.
"""

import pytest
import tempfile
from pathlib import Path

from repositories.filesystem import FileSystemRepository
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
        summary_of_qualifications=["10 years experience"],
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
    def test_save_and_get_job_posting(self, repository, sample_job_posting):
        repository.save_job_posting(sample_job_posting, "test-job")
        retrieved = repository.get_job_posting("test-job")

        assert retrieved is not None
        assert retrieved.company == "Acme Corp"
        assert retrieved.title == "Software Engineer"

    def test_list_job_postings(self, repository, sample_job_posting):
        repository.save_job_posting(sample_job_posting, "job-1")
        repository.save_job_posting(sample_job_posting, "job-2")

        listings = repository.list_job_postings()
        assert len(listings) == 2
        identifiers = [item["identifier"] for item in listings]
        assert "job-1" in identifiers
        assert "job-2" in identifiers

    def test_list_job_postings_empty(self, repository):
        listings = repository.list_job_postings()
        assert listings == []

    def test_delete_job_posting(self, repository, sample_job_posting):
        repository.save_job_posting(sample_job_posting, "to-delete")
        assert repository.delete_job_posting("to-delete") is True
        assert repository.get_job_posting("to-delete") is None

    def test_delete_nonexistent_job_posting(self, repository):
        assert repository.delete_job_posting("nonexistent") is False

    def test_save_job_posting_updates_existing(self, repository, sample_job_posting):
        repository.save_job_posting(sample_job_posting, "update-test")

        sample_job_posting.title = "Senior Software Engineer"
        repository.save_job_posting(sample_job_posting, "update-test")

        retrieved = repository.get_job_posting("update-test")
        assert retrieved.title == "Senior Software Engineer"

        listings = repository.list_job_postings()
        assert len(listings) == 1

    def test_job_posting_stored_in_correct_location(self, repository, sample_job_posting, temp_data_dir):
        repository.save_job_posting(sample_job_posting, "location-test")
        expected_path = Path(temp_data_dir) / "job-postings" / "location-test" / "job-posting.json"
        assert expected_path.exists()


class TestCvOperations:
    def test_save_and_get_cv(self, repository, sample_cv):
        repository.save_cv(sample_cv, "test-cv")
        retrieved = repository.get_cv("test-cv")

        assert retrieved is not None
        assert retrieved.name == "Jane Doe"
        assert retrieved.profession == "Software Engineer"

    def test_list_cvs(self, repository, sample_cv):
        repository.save_cv(sample_cv, "cv-1")
        repository.save_cv(sample_cv, "cv-2")

        listings = repository.list_cvs()
        assert len(listings) == 2
        identifiers = [item["identifier"] for item in listings]
        assert "cv-1" in identifiers
        assert "cv-2" in identifiers

    def test_list_cvs_empty(self, repository):
        listings = repository.list_cvs()
        assert listings == []

    def test_delete_cv(self, repository, sample_cv):
        repository.save_cv(sample_cv, "to-delete")
        assert repository.delete_cv("to-delete") is True
        assert repository.get_cv("to-delete") is None

    def test_delete_nonexistent_cv(self, repository):
        assert repository.delete_cv("nonexistent") is False

    def test_cv_stored_in_correct_location(self, repository, sample_cv, temp_data_dir):
        repository.save_cv(sample_cv, "location-test")
        expected_path = Path(temp_data_dir) / "cvs" / "location-test" / "cv.json"
        assert expected_path.exists()
