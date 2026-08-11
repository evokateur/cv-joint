"""
Unit tests for filesystem repository.
"""

import json
import pytest
import shutil
import tempfile
from pathlib import Path

from repositories import FileSystemRepository
from repositories.filesystem import parse_uri
from models import (
    CoverLetter,
    CurriculumVitae,
    CvTransformationPlan,
    JobPosting,
    OptimizedCvRecord,
)


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
        qualifications=["10 years experience"],
        education=[],
        experience=[],
        additional_experience=[],
        areas_of_expertise=[],
        languages=[],
    )


@pytest.fixture
def sample_cover_letter():
    from models import Contact

    return CoverLetter(
        name="Wesley Hinkle",
        contact=Contact(
            city="Oakland",
            state="CA",
            phone="+1-510-384-8010",
            email="wesley@evokateur.net",
        ),
        company="FrobozzCo",
        position="Sr. Magic Gunk Developer",
        salutation="Dear Hiring Manager,",
        closing="Sincerely,",
        paragraphs=["Interested in the xXposition role at xXcompany."],
    )


@pytest.fixture
def sample_plan():
    return CvTransformationPlan(
        job_title="Software Engineer",
        company="Acme Corp",
        matching_skills=["Python"],
        missing_skills=[],
    )


@pytest.fixture
def repository_with_job_posting(repository, sample_job_posting):
    repository.add_job_posting(sample_job_posting, "acme-swe")
    return repository


@pytest.fixture
def repository_with_cover_letter(repository, sample_cover_letter):
    repository.add_cover_letter(sample_cover_letter, "jane-acme")
    return repository


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
        assert all(
            item["identifier"] != "to-delete" for item in repository.list_job_postings()
        )

    def test_remove_nonexistent_job_posting(self, repository):
        assert repository.remove_job_posting("nonexistent") is False

    def test_add_job_posting_raises_if_exists(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "update-test")
        with pytest.raises(ValueError, match="already exists"):
            repository.add_job_posting(sample_job_posting, "update-test")

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

    def test_list_job_postings_excludes_filed_by_default(
        self, repository, sample_job_posting
    ):
        repository.add_job_posting(sample_job_posting, "active-job")
        repository.add_job_posting(sample_job_posting, "filed-job")
        repository.transition_job_posting("filed-job", "somewhere")

        listings = repository.list_job_postings()
        identifiers = [item["identifier"] for item in listings]
        assert "active-job" in identifiers
        assert "filed-job" not in identifiers

    def test_list_job_postings_by_location(self, repository, sample_job_posting):
        repository.add_job_posting(sample_job_posting, "active-job")
        repository.add_job_posting(sample_job_posting, "filed-job")
        repository.transition_job_posting("filed-job", "somewhere")

        listings = repository.list_job_postings(location="somewhere")
        identifiers = [item["identifier"] for item in listings]
        assert "active-job" not in identifiers
        assert "filed-job" in identifiers

    def test_list_job_postings_all_returns_every_record(
        self, repository, sample_job_posting
    ):
        repository.add_job_posting(sample_job_posting, "active-job")
        repository.add_job_posting(sample_job_posting, "filed-job")
        repository.transition_job_posting("filed-job", "somewhere")

        listings = repository.list_job_postings(all=True)
        identifiers = [item["identifier"] for item in listings]
        assert "active-job" in identifiers
        assert "filed-job" in identifiers


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
        expected_path = (
            Path(temp_data_dir) / "cvs" / "location-test" / "curriculum-vitae.json"
        )
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


class TestCoverLetterOperations:
    def test_add_and_get_cover_letter(self, repository, sample_cover_letter):
        repository.add_cover_letter(sample_cover_letter, "test-letter")
        retrieved = repository.get_cover_letter("test-letter")

        assert retrieved is not None
        assert retrieved.name == "Wesley Hinkle"
        assert retrieved.company == "FrobozzCo"
        assert retrieved.position == "Sr. Magic Gunk Developer"
        assert retrieved.salutation == "Dear Hiring Manager,"
        assert retrieved.closing == "Sincerely,"

    def test_list_cover_letters(self, repository, sample_cover_letter):
        repository.add_cover_letter(sample_cover_letter, "letter-1")
        repository.add_cover_letter(sample_cover_letter, "letter-2")

        listings = repository.list_cover_letters()
        assert len(listings) == 2
        identifiers = [item["identifier"] for item in listings]
        assert "letter-1" in identifiers
        assert "letter-2" in identifiers

    def test_list_cover_letters_empty(self, repository):
        assert repository.list_cover_letters() == []

    def test_remove_cover_letter(self, repository, sample_cover_letter, temp_data_dir):
        repository.add_cover_letter(sample_cover_letter, "to-delete")
        assert repository.remove_cover_letter("to-delete") is True
        assert repository.get_cover_letter("to-delete") is None
        assert not (Path(temp_data_dir) / "cover-letters" / "to-delete").exists()

    def test_remove_cover_letter_not_in_listing(self, repository, sample_cover_letter):
        repository.add_cover_letter(sample_cover_letter, "to-delete")
        repository.remove_cover_letter("to-delete")
        assert all(
            item["identifier"] != "to-delete"
            for item in repository.list_cover_letters()
        )

    def test_remove_nonexistent_cover_letter(self, repository):
        assert repository.remove_cover_letter("nonexistent") is False

    def test_add_cover_letter_raises_if_exists(self, repository, sample_cover_letter):
        repository.add_cover_letter(sample_cover_letter, "dupe")
        with pytest.raises(ValueError, match="already exists"):
            repository.add_cover_letter(sample_cover_letter, "dupe")

    def test_cover_letter_stored_in_correct_location(
        self, repository, sample_cover_letter, temp_data_dir
    ):
        repository.add_cover_letter(sample_cover_letter, "location-test")
        expected_path = (
            Path(temp_data_dir)
            / "cover-letters"
            / "location-test"
            / "cover-letter.json"
        )
        assert expected_path.exists()

    def test_get_cover_letter_record(self, repository, sample_cover_letter):
        repository.add_cover_letter(sample_cover_letter, "test-letter")
        record = repository.get_cover_letter_record("test-letter")

        assert record is not None
        assert record.identifier == "test-letter"
        assert record.path == "cover-letters/test-letter"
        assert record.name == "Wesley Hinkle"
        assert record.company == "FrobozzCo"
        assert record.position == "Sr. Magic Gunk Developer"
        assert record.created_at is not None

    def test_get_cover_letter_record_not_found(self, repository):
        assert repository.get_cover_letter_record("nonexistent") is None

    def test_draft_record_allows_optional_company_position(
        self, repository, sample_cover_letter
    ):
        draft = sample_cover_letter.model_copy(
            update={"company": None, "position": None}
        )
        repository.add_cover_letter(draft, "draft-letter")
        record = repository.get_cover_letter_record("draft-letter")

        assert record is not None
        assert record.company is None
        assert record.position is None


class TestRenameCoverLetter:
    def test_raises_when_not_found(self, repository):
        with pytest.raises(ValueError, match="not found"):
            repository.rename_cover_letter("nonexistent", "new-id")

    def test_raises_on_collision(self, repository, sample_cover_letter):
        repository.add_cover_letter(sample_cover_letter, "letter-1")
        repository.add_cover_letter(sample_cover_letter, "letter-2")
        with pytest.raises(ValueError, match="already exists"):
            repository.rename_cover_letter("letter-1", "letter-2")

    def test_renames_directory(self, repository, sample_cover_letter, temp_data_dir):
        repository.add_cover_letter(sample_cover_letter, "old-id")
        repository.rename_cover_letter("old-id", "new-id")
        assert not (Path(temp_data_dir) / "cover-letters" / "old-id").exists()
        assert (Path(temp_data_dir) / "cover-letters" / "new-id").exists()

    def test_updates_collection(self, repository, sample_cover_letter):
        repository.add_cover_letter(sample_cover_letter, "old-id")
        repository.rename_cover_letter("old-id", "new-id")
        assert repository.get_cover_letter_record("old-id") is None
        record = repository.get_cover_letter_record("new-id")
        assert record is not None
        assert record.identifier == "new-id"
        assert record.path == "cover-letters/new-id"

    def test_returns_new_record(self, repository, sample_cover_letter):
        repository.add_cover_letter(sample_cover_letter, "old-id")
        record = repository.rename_cover_letter("old-id", "new-id")
        assert record.identifier == "new-id"

    def test_preserves_created_at(self, repository, sample_cover_letter):
        repository.add_cover_letter(sample_cover_letter, "old-id")
        original = repository.get_cover_letter_record("old-id")
        record = repository.rename_cover_letter("old-id", "new-id")
        assert record.created_at == original.created_at


class TestOptimizedCvRecord:
    def test_constructs_with_required_fields(self):
        from models import OptimizedCvRecord
        from datetime import datetime

        record = OptimizedCvRecord(
            identifier="opt-1",
            path="job-postings/acme-swe/cvs/opt-1",
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

        assert not hasattr(
            OptimizedCvRecord.model_fields, "transformation_plan_filepath"
        )

    def test_optional_job_title_and_company(self):
        from models import OptimizedCvRecord
        from datetime import datetime

        record = OptimizedCvRecord(
            identifier="opt-1",
            path="job-postings/acme-swe/cvs/opt-1",
            job_posting_identifier="acme-swe",
            base_cv_identifier="jane-doe",
            name="Jane Doe",
            profession="Software Engineer",
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        )
        assert record.job_title is None
        assert record.company is None


class TestRemoveJobPostingCascadesOptimizedCvs:
    def test_cascades_to_optimized_cvs_collection(
        self, repository, sample_job_posting, sample_cv
    ):
        repository.add_job_posting(sample_job_posting, "to-delete")
        repository.add_optimized_cv("to-delete", "opt-1", "jane-doe", sample_cv)
        repository.add_optimized_cv("to-delete", "opt-2", "jane-doe", sample_cv)
        repository.remove_job_posting("to-delete")
        assert repository.list_optimized_cvs("to-delete") == []


class TestRenameJobPostingOptimizedCvs:
    def test_repairs_job_posting_identifier_in_optimized_cvs(
        self, repository, sample_job_posting, sample_cv
    ):
        repository.add_job_posting(sample_job_posting, "old-id")
        repository.add_optimized_cv("old-id", "opt-1", "jane-doe", sample_cv)
        repository.add_optimized_cv("old-id", "opt-2", "jane-doe", sample_cv)
        repository.rename_job_posting("old-id", "new-id")
        assert repository.get_optimized_cv_record("old-id", "opt-1") is None
        assert repository.get_optimized_cv_record("new-id", "opt-1") is not None
        assert (
            repository.get_optimized_cv_record("new-id", "opt-1").job_posting_identifier
            == "new-id"
        )
        assert (
            repository.get_optimized_cv_record("new-id", "opt-2").job_posting_identifier
            == "new-id"
        )


class TestRenameCvOptimizedCvs:
    def test_repairs_base_cv_identifier_in_optimized_cvs(
        self, repository, sample_job_posting, sample_cv
    ):
        repository.add_job_posting(sample_job_posting, "acme-swe")
        repository.add_cv(sample_cv, "old-cv")
        repository.add_optimized_cv("acme-swe", "opt-1", "old-cv", sample_cv)
        repository.add_optimized_cv("acme-swe", "opt-2", "old-cv", sample_cv)
        repository.rename_cv("old-cv", "new-cv")
        assert (
            repository.get_optimized_cv_record("acme-swe", "opt-1").base_cv_identifier
            == "new-cv"
        )
        assert (
            repository.get_optimized_cv_record("acme-swe", "opt-2").base_cv_identifier
            == "new-cv"
        )

    def test_does_not_repair_unrelated_optimizations(
        self, repository, sample_job_posting, sample_cv
    ):
        repository.add_job_posting(sample_job_posting, "acme-swe")
        repository.add_cv(sample_cv, "old-cv")
        repository.add_cv(sample_cv, "other-cv")
        repository.add_optimized_cv("acme-swe", "opt-1", "old-cv", sample_cv)
        repository.add_optimized_cv("acme-swe", "opt-2", "other-cv", sample_cv)
        repository.rename_cv("old-cv", "new-cv")
        assert (
            repository.get_optimized_cv_record("acme-swe", "opt-2").base_cv_identifier
            == "other-cv"
        )


class TestRemoveUsesStoredPath:
    def _move_to_custom_path(
        self, repository, collection_file, identifier, old_rel, new_rel
    ):
        old_abs = repository.data_dir / old_rel
        new_abs = repository.data_dir / new_rel
        new_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_abs), str(new_abs))

        collection = repository._load_collection(collection_file)
        for item in collection:
            if item["identifier"] == identifier:
                item["path"] = new_rel
                break
        repository._save_collection(collection_file, collection)

    def test_remove_job_posting_deletes_custom_path(
        self, repository, sample_job_posting, temp_data_dir
    ):
        repository.add_job_posting(sample_job_posting, "to-delete")
        self._move_to_custom_path(
            repository,
            repository.job_postings_collection,
            "to-delete",
            "job-postings/to-delete",
            "archived/job-postings/to-delete",
        )

        result = repository.remove_job_posting("to-delete")

        assert result is True
        assert not (Path(temp_data_dir) / "archived/job-postings/to-delete").exists()

    def test_remove_cv_deletes_custom_path(self, repository, sample_cv, temp_data_dir):
        repository.add_cv(sample_cv, "to-delete")
        self._move_to_custom_path(
            repository,
            repository.cvs_collection,
            "to-delete",
            "cvs/to-delete",
            "archived/cvs/to-delete",
        )

        result = repository.remove_cv("to-delete")

        assert result is True
        assert not (Path(temp_data_dir) / "archived/cvs/to-delete").exists()


class TestListCvsBaseOnly:
    def test_list_cvs_returns_only_base_cvs(
        self, repository, sample_job_posting, sample_cv
    ):
        repository.add_cv(sample_cv, "jane-doe")
        repository.add_job_posting(sample_job_posting, "acme-swe")
        repository.add_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
        listings = repository.list_cvs()
        assert len(listings) == 1
        assert listings[0]["identifier"] == "jane-doe"


class TestParseUri:
    def test_job_posting_uri(self):
        result = parse_uri("job-postings/acme-swe")
        assert result == {"collection": "job-postings", "identifier": "acme-swe"}

    def test_cv_uri(self):
        result = parse_uri("cvs/jane-doe")
        assert result == {"collection": "cvs", "identifier": "jane-doe"}

    def test_optimized_cv_uri(self):
        result = parse_uri("job-postings/acme-swe/cvs/jane-v2")
        assert result == {
            "collection": "optimized-cvs",
            "job_posting_identifier": "acme-swe",
            "identifier": "jane-v2",
        }

    def test_cover_letter_uri(self):
        result = parse_uri("cover-letters/frobozzco-magic-gunk")
        assert result == {
            "collection": "cover-letters",
            "identifier": "frobozzco-magic-gunk",
        }

    def test_strips_leading_slash(self):
        assert parse_uri("/job-postings/acme-swe") == parse_uri("job-postings/acme-swe")

    def test_raises_for_unrecognised_uri(self):
        with pytest.raises(ValueError, match="Unrecognised URI"):
            parse_uri("unknown/foo/bar")


class TestResolveRecord:
    def test_resolves_job_posting(self, repository, sample_job_posting):
        from models import JobPostingRecord

        repository.add_job_posting(sample_job_posting, "acme-swe")
        record = repository.resolve_record("job-postings/acme-swe")
        assert isinstance(record, JobPostingRecord)
        assert record.identifier == "acme-swe"

    def test_resolves_cv(self, repository, sample_cv):
        from models import CurriculumVitaeRecord

        repository.add_cv(sample_cv, "jane-doe")
        record = repository.resolve_record("cvs/jane-doe")
        assert isinstance(record, CurriculumVitaeRecord)
        assert record.identifier == "jane-doe"

    def test_resolves_optimized_cv(self, repository, sample_job_posting, sample_cv):
        from models import OptimizedCvRecord

        repository.add_job_posting(sample_job_posting, "acme-swe")
        repository.add_optimized_cv("acme-swe", "jane-v2", "jane-doe", sample_cv)
        record = repository.resolve_record("job-postings/acme-swe/cvs/jane-v2")
        assert isinstance(record, OptimizedCvRecord)
        assert record.identifier == "jane-v2"

    def test_resolves_cover_letter(self, repository, sample_cover_letter):
        from models import CoverLetterRecord

        repository.add_cover_letter(sample_cover_letter, "frobozzco-magic-gunk")
        record = repository.resolve_record("cover-letters/frobozzco-magic-gunk")
        assert isinstance(record, CoverLetterRecord)
        assert record.identifier == "frobozzco-magic-gunk"

    def test_raises_when_not_found(self, repository):
        with pytest.raises(ValueError, match="Not found"):
            repository.resolve_record("job-postings/nonexistent")


class TestRenameUsesStoredPath:
    def _move_to_custom_path(
        self, repository, collection_file, identifier, old_rel, new_rel
    ):
        old_abs = repository.data_dir / old_rel
        new_abs = repository.data_dir / new_rel
        new_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_abs), str(new_abs))
        collection = repository._load_collection(collection_file)
        for item in collection:
            if item["identifier"] == identifier:
                item["path"] = new_rel
                break
        repository._save_collection(collection_file, collection)

    def test_rename_job_posting_uses_stored_path(
        self, repository, sample_job_posting, temp_data_dir
    ):
        repository.add_job_posting(sample_job_posting, "old-id")
        self._move_to_custom_path(
            repository,
            repository.job_postings_collection,
            "old-id",
            "job-postings/old-id",
            "custom/old-id",
        )
        repository.rename_job_posting("old-id", "new-id")
        assert not (Path(temp_data_dir) / "custom/old-id").exists()
        assert (Path(temp_data_dir) / "custom/new-id").exists()

    def test_rename_cv_uses_stored_path(self, repository, sample_cv, temp_data_dir):
        repository.add_cv(sample_cv, "old-id")
        self._move_to_custom_path(
            repository,
            repository.cvs_collection,
            "old-id",
            "cvs/old-id",
            "custom/old-id",
        )
        repository.rename_cv("old-id", "new-id")
        assert not (Path(temp_data_dir) / "custom/old-id").exists()
        assert (Path(temp_data_dir) / "custom/new-id").exists()


class TestSaveObject:
    def test_writes_json_to_path_derived_from_class_name(
        self, repository, sample_plan, temp_data_dir
    ):
        repository.save_object("job-postings/acme-swe/cvs/opt-1", sample_plan)
        expected = (
            Path(temp_data_dir)
            / "job-postings"
            / "acme-swe"
            / "cvs"
            / "opt-1"
            / "cv-transformation-plan.json"
        )
        assert expected.exists()

    def test_includes_type_field(self, repository, sample_plan, temp_data_dir):
        repository.save_object("job-postings/acme-swe/cvs/opt-1", sample_plan)
        path = (
            Path(temp_data_dir)
            / "job-postings"
            / "acme-swe"
            / "cvs"
            / "opt-1"
            / "cv-transformation-plan.json"
        )
        data = json.loads(path.read_text())
        assert data["_type"] == "CvTransformationPlan"

    def test_creates_parent_directories(self, repository, sample_plan, temp_data_dir):
        repository.save_object("job-postings/new-job/cvs/new-opt", sample_plan)
        assert (
            Path(temp_data_dir) / "job-postings" / "new-job" / "cvs" / "new-opt"
        ).exists()

    def test_serializes_object_fields(self, repository, sample_plan, temp_data_dir):
        repository.save_object("job-postings/acme-swe/cvs/opt-1", sample_plan)
        path = (
            Path(temp_data_dir)
            / "job-postings"
            / "acme-swe"
            / "cvs"
            / "opt-1"
            / "cv-transformation-plan.json"
        )
        data = json.loads(path.read_text())
        assert data["job_title"] == "Software Engineer"
        assert data["company"] == "Acme Corp"


class TestLoadObject:
    def test_deserializes_to_typed_model(self, repository, sample_plan):
        repository.save_object("job-postings/acme-swe/cvs/opt-1", sample_plan)
        result = repository.load_object(
            "job-postings/acme-swe/cvs/opt-1", CvTransformationPlan
        )
        assert isinstance(result, CvTransformationPlan)
        assert result.job_title == "Software Engineer"

    def test_returns_none_when_not_found(self, repository):
        result = repository.load_object(
            "job-postings/acme-swe/cvs/opt-1", CvTransformationPlan
        )
        assert result is None


class TestLoadAllObjects:
    def test_returns_dict_keyed_by_stem(self, repository, sample_plan, sample_cv):
        repository.save_object("job-postings/acme-swe/cvs/opt-1", sample_plan)
        repository.save_object("job-postings/acme-swe/cvs/opt-1", sample_cv)
        result = repository.load_all_objects("job-postings/acme-swe/cvs/opt-1")
        assert "cv-transformation-plan" in result
        assert "curriculum-vitae" in result

    def test_deserializes_to_correct_types(self, repository, sample_plan):
        repository.save_object("job-postings/acme-swe/cvs/opt-1", sample_plan)
        result = repository.load_all_objects("job-postings/acme-swe/cvs/opt-1")
        assert isinstance(result["cv-transformation-plan"], CvTransformationPlan)

    def test_skips_files_without_type_field(self, repository, temp_data_dir):
        opt_dir = Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "opt-1"
        opt_dir.mkdir(parents=True)
        (opt_dir / "no-type.json").write_text('{"foo": "bar"}')
        result = repository.load_all_objects("job-postings/acme-swe/cvs/opt-1")
        assert "no-type" not in result

    def test_skips_files_with_unrecognised_type(self, repository, temp_data_dir):
        opt_dir = Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "opt-1"
        opt_dir.mkdir(parents=True)
        (opt_dir / "unknown.json").write_text(
            '{"_type": "SomeUnknownClass", "data": 1}'
        )
        result = repository.load_all_objects("job-postings/acme-swe/cvs/opt-1")
        assert "unknown" not in result

    def test_returns_empty_dict_for_nonexistent_directory(self, repository):
        result = repository.load_all_objects("job-postings/nonexistent/cvs/opt-1")
        assert result == {}


class TestAddOrReplaceDocument:
    def test_prepends_frontmatter_for_owned_stem(
        self, repository_with_job_posting, temp_data_dir
    ):
        repository_with_job_posting.add_or_replace_document(
            "job-postings/acme-swe/job-posting.md", "# Acme\n"
        )
        path = Path(temp_data_dir) / "job-postings" / "acme-swe" / "job-posting.md"
        content = path.read_text()
        assert content.startswith("---\n")
        assert "identifier: acme-swe" in content
        assert "# Acme" in content

    def test_prepends_frontmatter_for_cover_letter(
        self, repository_with_cover_letter, temp_data_dir
    ):
        repository_with_cover_letter.add_or_replace_document(
            "cover-letters/jane-acme/cover-letter.md", "# Letter\n"
        )
        path = Path(temp_data_dir) / "cover-letters" / "jane-acme" / "cover-letter.md"
        content = path.read_text()
        assert content.startswith("---\n")
        assert "identifier: jane-acme" in content
        assert "# Letter" in content

    def test_no_frontmatter_for_unowned_stem(
        self, repository_with_job_posting, temp_data_dir
    ):
        repository_with_job_posting.add_or_replace_document(
            "job-postings/acme-swe/readme.md", "# Notes\n"
        )
        path = Path(temp_data_dir) / "job-postings" / "acme-swe" / "readme.md"
        assert path.read_text() == "# Notes\n"

    def test_raises_for_unknown_uri(self, repository):
        with pytest.raises(ValueError):
            repository.add_or_replace_document(
                "job-postings/nonexistent/job-posting.md", "content"
            )

    def test_creates_directory_if_absent(
        self, repository_with_job_posting, temp_data_dir
    ):
        repository_with_job_posting.add_or_replace_document(
            "job-postings/acme-swe/job-posting.md", "content"
        )
        assert (Path(temp_data_dir) / "job-postings" / "acme-swe").exists()


class TestAddDocument:
    def test_raises_when_document_already_exists(self, repository_with_job_posting):
        repository_with_job_posting.add_document(
            "job-postings/acme-swe/notes.md", "# Notes\n"
        )
        with pytest.raises(ValueError, match="already exists"):
            repository_with_job_posting.add_document(
                "job-postings/acme-swe/notes.md", "# Overwrite\n"
            )

    def test_writes_document_when_absent(
        self, repository_with_job_posting, temp_data_dir
    ):
        repository_with_job_posting.add_document(
            "job-postings/acme-swe/notes.md", "# Notes\n"
        )
        path = Path(temp_data_dir) / "job-postings" / "acme-swe" / "notes.md"
        assert path.read_text() == "# Notes\n"


class TestLoadDocument:
    def test_reads_text_from_uri_path(self, repository_with_job_posting):
        repository_with_job_posting.add_or_replace_document(
            "job-postings/acme-swe/job-posting.md", "# Hello\n"
        )
        content = repository_with_job_posting.load_document(
            "job-postings/acme-swe/job-posting.md"
        )
        assert "# Hello" in content


class TestDocumentExists:
    def test_returns_true_when_file_exists(self, repository_with_job_posting):
        repository_with_job_posting.add_or_replace_document(
            "job-postings/acme-swe/job-posting.md", "content"
        )
        assert (
            repository_with_job_posting.document_exists(
                "job-postings/acme-swe/job-posting.md"
            )
            is True
        )

    def test_returns_false_when_file_absent(self, repository_with_job_posting):
        assert (
            repository_with_job_posting.document_exists(
                "job-postings/acme-swe/job-posting.md"
            )
            is False
        )


class TestPatchDocumentFrontmatter:
    def test_merges_record_fields_into_frontmatter(
        self, repository_with_job_posting, temp_data_dir
    ):
        repository_with_job_posting.add_or_replace_document(
            "job-postings/acme-swe/job-posting.md", "# Acme\n\nBody text.\n"
        )
        repository_with_job_posting.transition_job_posting("acme-swe", "somewhere")
        path = (
            Path(temp_data_dir)
            / "job-postings"
            / "somewhere"
            / "acme-swe"
            / "job-posting.md"
        )
        content = path.read_text()
        assert content.startswith("---\n")
        assert "location: somewhere" in content

    def test_preserves_hand_added_frontmatter_keys(
        self, repository_with_job_posting, temp_data_dir
    ):
        src = Path(temp_data_dir) / "job-postings" / "acme-swe" / "job-posting.md"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("---\ncustom_tag: keep-me\n---\n# Acme\n")
        repository_with_job_posting.transition_job_posting("acme-swe", "somewhere")
        path = (
            Path(temp_data_dir)
            / "job-postings"
            / "somewhere"
            / "acme-swe"
            / "job-posting.md"
        )
        assert "custom_tag: keep-me" in path.read_text()

    def test_preserves_body_content(self, repository_with_job_posting, temp_data_dir):
        repository_with_job_posting.add_or_replace_document(
            "job-postings/acme-swe/job-posting.md", "# Acme\n\nHand-edited paragraph.\n"
        )
        repository_with_job_posting.transition_job_posting("acme-swe", "somewhere")
        path = (
            Path(temp_data_dir)
            / "job-postings"
            / "somewhere"
            / "acme-swe"
            / "job-posting.md"
        )
        assert "Hand-edited paragraph." in path.read_text()

    def test_skips_nonexistent_markdown_files(self, repository_with_job_posting):
        # Should not raise even if no .md file exists yet
        repository_with_job_posting.transition_job_posting("acme-swe", "somewhere")


class TestUpsertOptimizedCv:
    def test_saves_curriculum_vitae_json_in_optimization_directory(
        self, repository_with_job_posting, sample_cv, temp_data_dir
    ):
        repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-1", "jane-doe", sample_cv
        )
        cv_path = (
            Path(temp_data_dir)
            / "job-postings"
            / "acme-swe"
            / "cvs"
            / "opt-1"
            / "curriculum-vitae.json"
        )
        assert cv_path.exists()

    def test_writes_record_to_collection(
        self, repository_with_job_posting, sample_cv, temp_data_dir
    ):
        repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-1", "jane-doe", sample_cv
        )
        collection_path = Path(temp_data_dir) / "collections" / "optimized-cvs.json"
        assert collection_path.exists()
        data = json.loads(collection_path.read_text())
        assert any(r["identifier"] == "opt-1" for r in data)

    def test_extracts_name_and_profession_from_cv(
        self, repository_with_job_posting, sample_cv
    ):
        record = repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-1", "jane-doe", sample_cv
        )
        assert record.name == "Jane Doe"
        assert record.profession == "Software Engineer"

    def test_looks_up_job_title_and_company_from_job_posting(
        self, repository_with_job_posting, sample_cv
    ):
        record = repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-1", "jane-doe", sample_cv
        )
        assert record.job_title == "Software Engineer"
        assert record.company == "Acme Corp"

    def test_returns_optimized_cv_record(self, repository_with_job_posting, sample_cv):
        record = repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-1", "jane-doe", sample_cv
        )
        assert isinstance(record, OptimizedCvRecord)
        assert record.identifier == "opt-1"
        assert record.job_posting_identifier == "acme-swe"
        assert record.base_cv_identifier == "jane-doe"


class TestGetOptimizedCvRecord:
    def test_returns_record(self, repository_with_job_posting, sample_cv):
        repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-1", "jane-doe", sample_cv
        )
        record = repository_with_job_posting.get_optimized_cv_record(
            "acme-swe", "opt-1"
        )
        assert record is not None
        assert isinstance(record, OptimizedCvRecord)
        assert record.identifier == "opt-1"

    def test_returns_none_when_not_found(self, repository_with_job_posting):
        assert (
            repository_with_job_posting.get_optimized_cv_record(
                "acme-swe", "nonexistent"
            )
            is None
        )


class TestGetOptimizedCv:
    def test_returns_curriculum_vitae(self, repository_with_job_posting, sample_cv):
        repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-1", "jane-doe", sample_cv
        )
        cv = repository_with_job_posting.get_optimized_cv("acme-swe", "opt-1")
        assert isinstance(cv, CurriculumVitae)
        assert cv.name == "Jane Doe"

    def test_returns_none_when_not_found(self, repository_with_job_posting):
        assert (
            repository_with_job_posting.get_optimized_cv("acme-swe", "nonexistent")
            is None
        )


class TestListOptimizedCvs:
    def test_returns_all_records(self, repository_with_job_posting, sample_cv):
        repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-1", "jane-doe", sample_cv
        )
        repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-2", "jane-doe", sample_cv
        )
        results = repository_with_job_posting.list_optimized_cvs()
        assert len(results) == 2

    def test_filters_by_job_posting_identifier(
        self, repository, sample_job_posting, sample_cv
    ):
        repository.add_job_posting(sample_job_posting, "acme-swe")
        repository.add_job_posting(sample_job_posting, "other-job")
        repository.add_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
        repository.add_optimized_cv("other-job", "opt-2", "jane-doe", sample_cv)
        results = repository.list_optimized_cvs("acme-swe")
        assert len(results) == 1
        assert results[0]["identifier"] == "opt-1"

    def test_returns_empty_list(self, repository_with_job_posting):
        assert repository_with_job_posting.list_optimized_cvs() == []


class TestRemoveOptimizedCv:
    def test_removes_from_collection_and_deletes_directory(
        self, repository_with_job_posting, sample_cv, temp_data_dir
    ):
        repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-1", "jane-doe", sample_cv
        )
        result = repository_with_job_posting.remove_optimized_cv("acme-swe", "opt-1")
        assert result is True
        assert (
            repository_with_job_posting.get_optimized_cv_record("acme-swe", "opt-1")
            is None
        )
        opt_dir = Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "opt-1"
        assert not opt_dir.exists()

    def test_returns_false_when_not_found(self, repository_with_job_posting):
        assert (
            repository_with_job_posting.remove_optimized_cv("acme-swe", "nonexistent")
            is False
        )


class TestRenameOptimizedCv:
    def test_renames_directory(
        self, repository_with_job_posting, sample_cv, temp_data_dir
    ):
        repository_with_job_posting.add_optimized_cv(
            "acme-swe", "old-id", "jane-doe", sample_cv
        )
        repository_with_job_posting.rename_optimized_cv("acme-swe", "old-id", "new-id")
        assert not (
            Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "old-id"
        ).exists()
        assert (
            Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "new-id"
        ).exists()

    def test_updates_collection(self, repository_with_job_posting, sample_cv):
        repository_with_job_posting.add_optimized_cv(
            "acme-swe", "old-id", "jane-doe", sample_cv
        )
        repository_with_job_posting.rename_optimized_cv("acme-swe", "old-id", "new-id")
        assert (
            repository_with_job_posting.get_optimized_cv_record("acme-swe", "old-id")
            is None
        )
        record = repository_with_job_posting.get_optimized_cv_record(
            "acme-swe", "new-id"
        )
        assert record is not None
        assert record.identifier == "new-id"

    def test_raises_when_not_found(self, repository_with_job_posting):
        with pytest.raises(ValueError, match="not found"):
            repository_with_job_posting.rename_optimized_cv(
                "acme-swe", "nonexistent", "new-id"
            )

    def test_raises_on_collision(self, repository_with_job_posting, sample_cv):
        repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-1", "jane-doe", sample_cv
        )
        repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-2", "jane-doe", sample_cv
        )
        with pytest.raises(ValueError, match="already exists"):
            repository_with_job_posting.rename_optimized_cv(
                "acme-swe", "opt-1", "opt-2"
            )


class TestOptimizedCvUsesParentPath:
    """Optimized CV path operations must use the stored JobPostingRecord.path, not reconstruct from identifiers.

    Regression tests for CJ-17: operations break when a job posting's path in the collection
    index differs from the default `job-postings/{identifier}` (e.g. after archiving/moving).
    """

    def _move_job_posting(self, repository, identifier, new_rel):
        """Physically move a job posting directory and update its stored path in the collection."""
        collection = repository._load_collection(repository.job_postings_collection)
        item = next(i for i in collection if i["identifier"] == identifier)
        old_abs = repository.data_dir / item["path"]
        new_abs = repository.data_dir / new_rel
        new_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_abs), str(new_abs))
        item["path"] = new_rel
        repository._save_collection(repository.job_postings_collection, collection)

    def test_add_optimized_cv_saves_under_parent_stored_path(
        self, repository_with_job_posting, sample_cv, temp_data_dir
    ):
        self._move_job_posting(
            repository_with_job_posting, "acme-swe", "job-postings/archived/acme-swe"
        )
        repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-1", "jane-doe", sample_cv
        )
        correct = (
            Path(temp_data_dir)
            / "job-postings/archived/acme-swe/cvs/opt-1/curriculum-vitae.json"
        )
        assert correct.exists()

    def test_get_optimized_cv_reads_from_parent_stored_path(
        self, repository_with_job_posting, sample_cv
    ):
        repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-1", "jane-doe", sample_cv
        )
        # Moving the job posting dir carries the nested cvs/opt-1 subdir with it.
        self._move_job_posting(
            repository_with_job_posting, "acme-swe", "job-postings/archived/acme-swe"
        )
        result = repository_with_job_posting.get_optimized_cv("acme-swe", "opt-1")
        assert result is not None

    def test_remove_optimized_cv_deletes_from_parent_stored_path(
        self, repository_with_job_posting, sample_cv, temp_data_dir
    ):
        repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-1", "jane-doe", sample_cv
        )
        self._move_job_posting(
            repository_with_job_posting, "acme-swe", "job-postings/archived/acme-swe"
        )
        cv_dir = Path(temp_data_dir) / "job-postings/archived/acme-swe/cvs/opt-1"
        assert cv_dir.exists()
        repository_with_job_posting.remove_optimized_cv("acme-swe", "opt-1")
        assert not cv_dir.exists()

    def test_rename_optimized_cv_uses_parent_stored_path(
        self, repository_with_job_posting, sample_cv, temp_data_dir
    ):
        repository_with_job_posting.add_optimized_cv(
            "acme-swe", "old-id", "jane-doe", sample_cv
        )
        self._move_job_posting(
            repository_with_job_posting, "acme-swe", "job-postings/archived/acme-swe"
        )
        repository_with_job_posting.rename_optimized_cv("acme-swe", "old-id", "new-id")
        assert not (
            Path(temp_data_dir) / "job-postings/archived/acme-swe/cvs/old-id"
        ).exists()
        assert (
            Path(temp_data_dir) / "job-postings/archived/acme-swe/cvs/new-id"
        ).exists()


class TestTransitionAuditLog:
    def test_sets_location(self, repository_with_job_posting):
        record = repository_with_job_posting.transition_job_posting(
            "acme-swe", "somewhere"
        )
        assert record.location == "somewhere"
        assert (
            repository_with_job_posting.get_job_posting_record("acme-swe").location
            == "somewhere"
        )

    def test_updates_updated_at(self, repository_with_job_posting):
        from datetime import datetime

        before = datetime.now()
        record = repository_with_job_posting.transition_job_posting(
            "acme-swe", "somewhere"
        )
        assert record.updated_at >= before

    def test_merges_record_fields_into_record(self, repository_with_job_posting):
        record = repository_with_job_posting.transition_job_posting(
            "acme-swe", "somewhere", record_fields={"applied_with": "my-cv"}
        )
        assert record.applied_with == "my-cv"
        assert (
            repository_with_job_posting.get_job_posting_record("acme-swe").applied_with
            == "my-cv"
        )

    def test_raises_when_already_in_target_location(self, repository_with_job_posting):
        repository_with_job_posting.transition_job_posting("acme-swe", "somewhere")
        with pytest.raises(ValueError, match="already in "):
            repository_with_job_posting.transition_job_posting("acme-swe", "somewhere")

    def test_appends_entry_with_required_keys(self, repository_with_job_posting):
        record = repository_with_job_posting.transition_job_posting(
            "acme-swe", "applied"
        )
        assert len(record.transitions) == 1
        entry = record.transitions[0]
        assert entry["location"] == "applied"
        assert "date" in entry

    def test_arbitrary_fields_included_in_entry(self, repository_with_job_posting):
        record = repository_with_job_posting.transition_job_posting(
            "acme-swe", "applied", {"note": "strong match"}
        )
        assert record.transitions[0]["note"] == "strong match"

    def test_subsequent_transitions_append_not_replace(
        self, repository_with_job_posting
    ):
        repository_with_job_posting.transition_job_posting("acme-swe", "applied")
        record = repository_with_job_posting.transition_job_posting(
            "acme-swe", "archived"
        )
        assert len(record.transitions) == 2
        assert record.transitions[0]["location"] == "applied"
        assert record.transitions[1]["location"] == "archived"

    def test_dot_stored_verbatim_in_log_normalized_on_record(
        self, repository_with_job_posting
    ):
        repository_with_job_posting.transition_job_posting("acme-swe", "archived")
        record = repository_with_job_posting.transition_job_posting("acme-swe", ".")
        assert record.location is None
        assert record.transitions[-1]["location"] == "."
