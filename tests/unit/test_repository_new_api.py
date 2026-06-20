"""
Tests for new repository API introduced in step 2:
save_object, load_object, load_all_objects, save_document, load_document,
document_exists, add_optimized_cv, get_optimized_cv_record, get_optimized_cv,
list_optimized_cvs, remove_optimized_cv, rename_optimized_cv, purge_optimized_cv.
"""

import json
import shutil
import pytest
import tempfile
from pathlib import Path

from repositories import FileSystemRepository
from models import (
    CurriculumVitae,
    Contact,
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
def sample_cv():
    return CurriculumVitae(
        name="Jane Doe",
        profession="Software Engineer",
        contact=Contact(
            city="San Francisco", state="CA",
            email="jane@example.com", phone="555-1234",
            linkedin="linkedin.com/in/janedoe", github="github.com/janedoe",
        ),
        core_expertise=["Python"],
        summary_of_qualifications="10 years experience",
        education=[], experience=[], additional_experience=[],
        areas_of_expertise=[], languages=[],
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


@pytest.fixture
def repository_with_job_posting(repository, sample_job_posting):
    repository.add_job_posting(sample_job_posting, "acme-swe")
    return repository


class TestSaveObject:
    def test_writes_json_to_path_derived_from_class_name(
        self, repository, sample_plan, temp_data_dir
    ):
        repository.save_object("job-postings/acme-swe/cvs/opt-1", sample_plan)
        expected = Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "opt-1" / "cv-transformation-plan.json"
        assert expected.exists()

    def test_includes_type_field(self, repository, sample_plan, temp_data_dir):
        repository.save_object("job-postings/acme-swe/cvs/opt-1", sample_plan)
        path = Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "opt-1" / "cv-transformation-plan.json"
        data = json.loads(path.read_text())
        assert data["_type"] == "CvTransformationPlan"

    def test_creates_parent_directories(self, repository, sample_plan, temp_data_dir):
        repository.save_object("job-postings/new-job/cvs/new-opt", sample_plan)
        assert (Path(temp_data_dir) / "job-postings" / "new-job" / "cvs" / "new-opt").exists()

    def test_serializes_object_fields(self, repository, sample_plan, temp_data_dir):
        repository.save_object("job-postings/acme-swe/cvs/opt-1", sample_plan)
        path = Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "opt-1" / "cv-transformation-plan.json"
        data = json.loads(path.read_text())
        assert data["job_title"] == "Software Engineer"
        assert data["company"] == "Acme Corp"


class TestLoadObject:
    def test_deserializes_to_typed_model(self, repository, sample_plan):
        repository.save_object("job-postings/acme-swe/cvs/opt-1", sample_plan)
        result = repository.load_object("job-postings/acme-swe/cvs/opt-1", CvTransformationPlan)
        assert isinstance(result, CvTransformationPlan)
        assert result.job_title == "Software Engineer"

    def test_returns_none_when_not_found(self, repository):
        result = repository.load_object("job-postings/acme-swe/cvs/opt-1", CvTransformationPlan)
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
        (opt_dir / "unknown.json").write_text('{"_type": "SomeUnknownClass", "data": 1}')
        result = repository.load_all_objects("job-postings/acme-swe/cvs/opt-1")
        assert "unknown" not in result

    def test_returns_empty_dict_for_nonexistent_directory(self, repository):
        result = repository.load_all_objects("job-postings/nonexistent/cvs/opt-1")
        assert result == {}


class TestSaveDocument:
    def test_prepends_frontmatter_for_owned_stem(self, repository_with_job_posting, temp_data_dir):
        repository_with_job_posting.save_document("job-postings/acme-swe/job-posting.md", "# Acme\n")
        path = Path(temp_data_dir) / "job-postings" / "acme-swe" / "job-posting.md"
        content = path.read_text()
        assert content.startswith("---\n")
        assert "identifier: acme-swe" in content
        assert "# Acme" in content

    def test_no_frontmatter_for_unowned_stem(self, repository_with_job_posting, temp_data_dir):
        repository_with_job_posting.save_document("job-postings/acme-swe/readme.md", "# Notes\n")
        path = Path(temp_data_dir) / "job-postings" / "acme-swe" / "readme.md"
        assert path.read_text() == "# Notes\n"

    def test_raises_for_unknown_uri(self, repository):
        with pytest.raises(ValueError):
            repository.save_document("job-postings/nonexistent/job-posting.md", "content")

    def test_creates_directory_if_absent(self, repository_with_job_posting, temp_data_dir):
        repository_with_job_posting.save_document("job-postings/acme-swe/job-posting.md", "content")
        assert (Path(temp_data_dir) / "job-postings" / "acme-swe").exists()


class TestLoadDocument:
    def test_reads_text_from_uri_path(self, repository_with_job_posting):
        repository_with_job_posting.save_document("job-postings/acme-swe/job-posting.md", "# Hello\n")
        content = repository_with_job_posting.load_document("job-postings/acme-swe/job-posting.md")
        assert "# Hello" in content


class TestDocumentExists:
    def test_returns_true_when_file_exists(self, repository_with_job_posting):
        repository_with_job_posting.save_document("job-postings/acme-swe/job-posting.md", "content")
        assert repository_with_job_posting.document_exists("job-postings/acme-swe/job-posting.md") is True

    def test_returns_false_when_file_absent(self, repository_with_job_posting):
        assert repository_with_job_posting.document_exists("job-postings/acme-swe/job-posting.md") is False


class TestPatchDocumentFrontmatter:
    def test_merges_record_fields_into_frontmatter(
        self, repository_with_job_posting, temp_data_dir
    ):
        repository_with_job_posting.save_document(
            "job-postings/acme-swe/job-posting.md", "# Acme\n\nBody text.\n"
        )
        repository_with_job_posting.archive_job_posting("acme-swe")
        path = Path(temp_data_dir) / "job-postings" / "archived" / "acme-swe" / "job-posting.md"
        content = path.read_text()
        assert content.startswith("---\n")
        assert "location: archived" in content

    def test_preserves_hand_added_frontmatter_keys(
        self, repository_with_job_posting, temp_data_dir
    ):
        src = Path(temp_data_dir) / "job-postings" / "acme-swe" / "job-posting.md"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("---\ncustom_tag: keep-me\n---\n# Acme\n")
        repository_with_job_posting.archive_job_posting("acme-swe")
        path = Path(temp_data_dir) / "job-postings" / "archived" / "acme-swe" / "job-posting.md"
        assert "custom_tag: keep-me" in path.read_text()

    def test_preserves_body_content(self, repository_with_job_posting, temp_data_dir):
        repository_with_job_posting.save_document(
            "job-postings/acme-swe/job-posting.md", "# Acme\n\nHand-edited paragraph.\n"
        )
        repository_with_job_posting.archive_job_posting("acme-swe")
        path = Path(temp_data_dir) / "job-postings" / "archived" / "acme-swe" / "job-posting.md"
        assert "Hand-edited paragraph." in path.read_text()

    def test_skips_nonexistent_markdown_files(self, repository_with_job_posting):
        # Should not raise even if no .md file exists yet
        repository_with_job_posting.archive_job_posting("acme-swe")

    def test_skips_file_with_missing_frontmatter_block(
        self, repository_with_job_posting, temp_data_dir
    ):
        path = Path(temp_data_dir) / "job-postings" / "acme-swe" / "job-posting.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# No frontmatter here\n")
        # Should not raise; file without frontmatter is skipped gracefully
        record = repository_with_job_posting.archive_job_posting("acme-swe")
        assert record.location == "archived"
        moved = Path(temp_data_dir) / "job-postings" / "archived" / "acme-swe" / "job-posting.md"
        assert "# No frontmatter here" in moved.read_text()


class TestUpsertOptimizedCv:
    def test_saves_curriculum_vitae_json_in_optimization_directory(
        self, repository_with_job_posting, sample_cv, temp_data_dir
    ):
        repository_with_job_posting.add_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
        cv_path = Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "opt-1" / "curriculum-vitae.json"
        assert cv_path.exists()

    def test_writes_record_to_collection(
        self, repository_with_job_posting, sample_cv, temp_data_dir
    ):
        repository_with_job_posting.add_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
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

    def test_returns_optimized_cv_record(
        self, repository_with_job_posting, sample_cv
    ):
        record = repository_with_job_posting.add_optimized_cv(
            "acme-swe", "opt-1", "jane-doe", sample_cv
        )
        assert isinstance(record, OptimizedCvRecord)
        assert record.identifier == "opt-1"
        assert record.job_posting_identifier == "acme-swe"
        assert record.base_cv_identifier == "jane-doe"


class TestGetOptimizedCvRecord:
    def test_returns_record(self, repository_with_job_posting, sample_cv):
        repository_with_job_posting.add_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
        record = repository_with_job_posting.get_optimized_cv_record("acme-swe", "opt-1")
        assert record is not None
        assert isinstance(record, OptimizedCvRecord)
        assert record.identifier == "opt-1"

    def test_returns_none_when_not_found(self, repository_with_job_posting):
        assert repository_with_job_posting.get_optimized_cv_record("acme-swe", "nonexistent") is None


class TestGetOptimizedCv:
    def test_returns_curriculum_vitae(self, repository_with_job_posting, sample_cv):
        repository_with_job_posting.add_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
        cv = repository_with_job_posting.get_optimized_cv("acme-swe", "opt-1")
        assert isinstance(cv, CurriculumVitae)
        assert cv.name == "Jane Doe"

    def test_returns_none_when_not_found(self, repository_with_job_posting):
        assert repository_with_job_posting.get_optimized_cv("acme-swe", "nonexistent") is None


class TestListOptimizedCvs:
    def test_returns_all_records(self, repository_with_job_posting, sample_cv):
        repository_with_job_posting.add_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
        repository_with_job_posting.add_optimized_cv("acme-swe", "opt-2", "jane-doe", sample_cv)
        results = repository_with_job_posting.list_optimized_cvs()
        assert len(results) == 2

    def test_filters_by_job_posting_identifier(self, repository, sample_job_posting, sample_cv):
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
        repository_with_job_posting.add_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
        result = repository_with_job_posting.remove_optimized_cv("acme-swe", "opt-1")
        assert result is True
        assert repository_with_job_posting.get_optimized_cv_record("acme-swe", "opt-1") is None
        opt_dir = Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "opt-1"
        assert not opt_dir.exists()

    def test_returns_false_when_not_found(self, repository_with_job_posting):
        assert repository_with_job_posting.remove_optimized_cv("acme-swe", "nonexistent") is False


class TestRenameOptimizedCv:
    def test_renames_directory(
        self, repository_with_job_posting, sample_cv, temp_data_dir
    ):
        repository_with_job_posting.add_optimized_cv("acme-swe", "old-id", "jane-doe", sample_cv)
        repository_with_job_posting.rename_optimized_cv("acme-swe", "old-id", "new-id")
        assert not (Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "old-id").exists()
        assert (Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "new-id").exists()

    def test_updates_collection(self, repository_with_job_posting, sample_cv):
        repository_with_job_posting.add_optimized_cv("acme-swe", "old-id", "jane-doe", sample_cv)
        repository_with_job_posting.rename_optimized_cv("acme-swe", "old-id", "new-id")
        assert repository_with_job_posting.get_optimized_cv_record("acme-swe", "old-id") is None
        record = repository_with_job_posting.get_optimized_cv_record("acme-swe", "new-id")
        assert record is not None
        assert record.identifier == "new-id"

    def test_raises_when_not_found(self, repository_with_job_posting):
        with pytest.raises(ValueError, match="not found"):
            repository_with_job_posting.rename_optimized_cv("acme-swe", "nonexistent", "new-id")

    def test_raises_on_collision(self, repository_with_job_posting, sample_cv):
        repository_with_job_posting.add_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
        repository_with_job_posting.add_optimized_cv("acme-swe", "opt-2", "jane-doe", sample_cv)
        with pytest.raises(ValueError, match="already exists"):
            repository_with_job_posting.rename_optimized_cv("acme-swe", "opt-1", "opt-2")


class TestPurgeOptimizedCv:
    def test_deletes_directory(
        self, repository_with_job_posting, sample_cv, temp_data_dir
    ):
        repository_with_job_posting.add_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
        result = repository_with_job_posting.purge_optimized_cv("acme-swe", "opt-1")
        assert result is True
        opt_dir = Path(temp_data_dir) / "job-postings" / "acme-swe" / "cvs" / "opt-1"
        assert not opt_dir.exists()

    def test_does_not_remove_collection_entry(
        self, repository_with_job_posting, sample_cv
    ):
        repository_with_job_posting.add_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
        repository_with_job_posting.purge_optimized_cv("acme-swe", "opt-1")
        assert repository_with_job_posting.get_optimized_cv_record("acme-swe", "opt-1") is not None

    def test_returns_false_when_directory_not_found(self, repository_with_job_posting):
        assert repository_with_job_posting.purge_optimized_cv("acme-swe", "nonexistent") is False


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
        repository_with_job_posting.add_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
        correct = Path(temp_data_dir) / "job-postings/archived/acme-swe/cvs/opt-1/curriculum-vitae.json"
        assert correct.exists()

    def test_get_optimized_cv_reads_from_parent_stored_path(
        self, repository_with_job_posting, sample_cv
    ):
        repository_with_job_posting.add_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
        # Moving the job posting dir carries the nested cvs/opt-1 subdir with it.
        self._move_job_posting(
            repository_with_job_posting, "acme-swe", "job-postings/archived/acme-swe"
        )
        result = repository_with_job_posting.get_optimized_cv("acme-swe", "opt-1")
        assert result is not None

    def test_remove_optimized_cv_deletes_from_parent_stored_path(
        self, repository_with_job_posting, sample_cv, temp_data_dir
    ):
        repository_with_job_posting.add_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
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
        repository_with_job_posting.add_optimized_cv("acme-swe", "old-id", "jane-doe", sample_cv)
        self._move_job_posting(
            repository_with_job_posting, "acme-swe", "job-postings/archived/acme-swe"
        )
        repository_with_job_posting.rename_optimized_cv("acme-swe", "old-id", "new-id")
        assert not (Path(temp_data_dir) / "job-postings/archived/acme-swe/cvs/old-id").exists()
        assert (Path(temp_data_dir) / "job-postings/archived/acme-swe/cvs/new-id").exists()

    def test_purge_optimized_cv_deletes_from_parent_stored_path(
        self, repository_with_job_posting, sample_cv, temp_data_dir
    ):
        repository_with_job_posting.add_optimized_cv("acme-swe", "opt-1", "jane-doe", sample_cv)
        self._move_job_posting(
            repository_with_job_posting, "acme-swe", "job-postings/archived/acme-swe"
        )
        cv_dir = Path(temp_data_dir) / "job-postings/archived/acme-swe/cvs/opt-1"
        assert cv_dir.exists()
        result = repository_with_job_posting.purge_optimized_cv("acme-swe", "opt-1")
        assert result is True
        assert not cv_dir.exists()


class TestTransitionAuditLog:
    def test_appends_entry_with_required_keys(self, repository_with_job_posting):
        record = repository_with_job_posting.transition_job_posting("acme-swe", "applied")
        assert len(record.transitions) == 1
        entry = record.transitions[0]
        assert entry["location"] == "applied"
        assert "date" in entry

    def test_arbitrary_fields_included_in_entry(self, repository_with_job_posting):
        record = repository_with_job_posting.transition_job_posting(
            "acme-swe", "applied", {"note": "strong match"}
        )
        assert record.transitions[0]["note"] == "strong match"

    def test_subsequent_transitions_append_not_replace(self, repository_with_job_posting):
        repository_with_job_posting.transition_job_posting("acme-swe", "applied")
        record = repository_with_job_posting.transition_job_posting("acme-swe", "archived")
        assert len(record.transitions) == 2
        assert record.transitions[0]["location"] == "applied"
        assert record.transitions[1]["location"] == "archived"

    def test_dot_stored_verbatim_in_log_normalized_on_record(self, repository_with_job_posting):
        repository_with_job_posting.transition_job_posting("acme-swe", "archived")
        record = repository_with_job_posting.transition_job_posting("acme-swe", ".")
        assert record.location is None
        assert record.transitions[-1]["location"] == "."
