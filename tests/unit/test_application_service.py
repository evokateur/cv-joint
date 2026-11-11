"""
Application behavior and explicit Markdown export tests.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_generate_pdf_file_renders_data_to_explicit_output(service, sample_cv_data):
    output_path = "/tmp/example.pdf"

    with (
        patch(
            "services.application.render_tex", return_value="tex source"
        ) as render_tex,
        patch(
            "services.application.tex_to_pdf", return_value=output_path
        ) as tex_to_pdf,
    ):
        result = service.generate_pdf_file(sample_cv_data, "cv.tex", output_path)

    assert result == output_path
    render_tex.assert_called_once_with(sample_cv_data, "cv.tex")
    tex_to_pdf.assert_called_once_with("tex source", output_path)


class TestExportJobPostingMarkdown:
    def test_includes_record_frontmatter(self, service, sample_job_posting_data):
        service.add_job_posting(sample_job_posting_data, "test-job")
        service.export_markdown()
        record = service.repository.get_job_posting_record("test-job")
        content = service.repository.load_document(record, "job-posting.md")
        assert content.startswith("---\nidentifier: test-job\n")
        assert "path: job-postings/test-job\n" in content

    def test_creates_markdown(self, service, sample_job_posting_data, temp_data_dir):
        service.add_job_posting(sample_job_posting_data, "test-job")
        service.export_markdown()
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

        service.add_job_posting(data, "no-company")
        service.export_markdown()
        md_path = Path(temp_data_dir) / "job-postings" / "no-company" / "job-posting.md"
        content = md_path.read_text()
        assert "# Developer\n" in content
        assert "at Not specified" not in content


class TestExportCvMarkdown:
    def test_creates_markdown(self, service, sample_cv_data, temp_data_dir):
        service.add_cv(sample_cv_data, "test-cv")
        service.export_markdown()
        md_path = Path(temp_data_dir) / "cvs" / "test-cv" / "curriculum-vitae.md"
        assert md_path.exists()
        content = md_path.read_text()
        assert "# Jane Doe" in content


class TestExportMarkdown:
    def test_export_all(
        self, service, sample_job_posting_data, sample_cv_data, temp_data_dir
    ):
        service.add_job_posting(sample_job_posting_data, "job-1")
        service.add_cv(sample_cv_data, "cv-1")

        job_md = Path(temp_data_dir) / "job-postings" / "job-1" / "job-posting.md"
        cv_md = Path(temp_data_dir) / "cvs" / "cv-1" / "curriculum-vitae.md"

        count = service.export_markdown()
        assert count == 2
        assert job_md.exists()
        assert cv_md.exists()

    def test_export_by_collection(
        self, service, sample_job_posting_data, sample_cv_data, temp_data_dir
    ):
        service.add_job_posting(sample_job_posting_data, "job-1")
        service.add_cv(sample_cv_data, "cv-1")

        job_md = Path(temp_data_dir) / "job-postings" / "job-1" / "job-posting.md"
        cv_md = Path(temp_data_dir) / "cvs" / "cv-1" / "curriculum-vitae.md"

        count = service.export_markdown(collection_name="job-postings")
        assert count == 1
        assert job_md.exists()
        assert not cv_md.exists()

    def test_export_optimizations(
        self,
        service,
        sample_job_posting_data,
        sample_cv_data,
        temp_data_dir,
        build_optimized_cv_record,
    ):
        service.add_job_posting(sample_job_posting_data, "job-1")
        service.add_cv(sample_cv_data, "cv-1")

        plan = CvTransformationPlan(job_title="Software Engineer", company="Acme Corp")
        cv = CurriculumVitae(**sample_cv_data)
        record = service.repository.add_optimized_cv(
            service.repository.get_job_posting_record("job-1"),
            build_optimized_cv_record("opt-1", "job-1", "cv-1"),
            cv,
        )
        service.repository.save_object(record, plan)

        opt_dir = Path(temp_data_dir) / "job-postings" / "job-1" / "cvs" / "opt-1"
        plan_md = opt_dir / "cv-transformation-plan.md"
        cv_md = opt_dir / "curriculum-vitae.md"

        count = service.export_markdown(collection_name="optimizations")
        assert count == 2
        assert plan_md.exists()
        assert cv_md.exists()

    def test_export_cvs_excludes_optimized(
        self,
        service,
        sample_job_posting_data,
        sample_cv_data,
        build_optimized_cv_record,
    ):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        service.add_cv(sample_cv_data, "jane-doe")
        service.repository.add_optimized_cv(
            service.repository.get_job_posting_record("acme-swe"),
            build_optimized_cv_record("opt-1", "acme-swe", "jane-doe"),
            CurriculumVitae(**sample_cv_data),
        )

        count = service.export_markdown(collection_name="cvs")
        assert count == 1

    def test_unknown_collection_raises(self, service):
        with pytest.raises(ValueError, match="Unknown collection: invalid"):
            service.export_markdown(collection_name="invalid")


class TestRemoveJobPosting:
    def test_returns_true_when_found(self, service, sample_job_posting_data):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        assert service.remove_job_posting("acme-swe") is True

    def test_returns_false_when_not_found(self, service):
        assert service.remove_job_posting("nonexistent") is False

    def test_removes_from_repository(self, service, sample_job_posting_data):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        service.remove_job_posting("acme-swe")
        assert service.get_job_posting("acme-swe") is None

    def test_deletes_markdown(self, service, sample_job_posting_data, temp_data_dir):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        service.add_document(
            "job-postings/acme-swe/job-posting.md", b"# Existing document\n"
        )
        md_path = Path(temp_data_dir) / "job-postings" / "acme-swe" / "job-posting.md"
        assert md_path.exists()
        service.remove_job_posting("acme-swe")
        assert not md_path.exists()


class TestRemoveCv:
    def test_returns_true_when_found(self, service, sample_cv_data):
        service.add_cv(sample_cv_data, "jane-doe")
        assert service.remove_cv("jane-doe") is True

    def test_returns_false_when_not_found(self, service):
        assert service.remove_cv("nonexistent") is False

    def test_removes_from_repository(self, service, sample_cv_data):
        service.add_cv(sample_cv_data, "jane-doe")
        service.remove_cv("jane-doe")
        assert service.get_cv("jane-doe") is None

    def test_deletes_markdown(self, service, sample_cv_data, temp_data_dir):
        service.add_cv(sample_cv_data, "jane-doe")
        service.add_document(
            "cvs/jane-doe/curriculum-vitae.md", b"# Existing document\n"
        )
        md_path = Path(temp_data_dir) / "cvs" / "jane-doe" / "curriculum-vitae.md"
        assert md_path.exists()
        service.remove_cv("jane-doe")
        assert not md_path.exists()


class TestRenameJobPosting:
    def test_raises_when_not_found(self, service):
        with pytest.raises(ValueError, match="not found"):
            service.rename_job_posting("nonexistent", "new-id")

    def test_raises_on_collision(self, service, sample_job_posting_data):
        service.add_job_posting(sample_job_posting_data, "job-1")
        service.add_job_posting(sample_job_posting_data, "job-2")
        with pytest.raises(ValueError, match="already exists"):
            service.rename_job_posting("job-1", "job-2")

    def test_data_accessible_at_new_identifier(self, service, sample_job_posting_data):
        service.add_job_posting(sample_job_posting_data, "old-id")
        service.rename_job_posting("old-id", "new-id")
        assert service.get_job_posting("old-id") is None
        assert service.get_job_posting("new-id") is not None

    def test_moves_markdown(self, service, sample_job_posting_data, temp_data_dir):
        service.add_job_posting(sample_job_posting_data, "old-id")
        service.add_document(
            "job-postings/old-id/job-posting.md", b"# Existing document\n"
        )
        service.rename_job_posting("old-id", "new-id")
        assert not (Path(temp_data_dir) / "job-postings" / "old-id").exists()
        assert (
            Path(temp_data_dir) / "job-postings" / "new-id" / "job-posting.md"
        ).exists()


class TestRenameCv:
    def test_raises_when_not_found(self, service):
        with pytest.raises(ValueError, match="not found"):
            service.rename_cv("nonexistent", "new-id")

    def test_raises_on_collision(self, service, sample_cv_data):
        service.add_cv(sample_cv_data, "cv-1")
        service.add_cv(sample_cv_data, "cv-2")
        with pytest.raises(ValueError, match="already exists"):
            service.rename_cv("cv-1", "cv-2")

    def test_data_accessible_at_new_identifier(self, service, sample_cv_data):
        service.add_cv(sample_cv_data, "old-id")
        service.rename_cv("old-id", "new-id")
        assert service.get_cv("old-id") is None
        assert service.get_cv("new-id") is not None

    def test_moves_markdown(self, service, sample_cv_data, temp_data_dir):
        service.add_cv(sample_cv_data, "old-id")
        service.add_document("cvs/old-id/curriculum-vitae.md", b"# Existing document\n")
        service.rename_cv("old-id", "new-id")
        assert not (Path(temp_data_dir) / "cvs" / "old-id").exists()
        assert (Path(temp_data_dir) / "cvs" / "new-id" / "curriculum-vitae.md").exists()

    def test_repairs_optimization_references(
        self,
        service,
        sample_job_posting_data,
        sample_cv_data,
        build_optimized_cv_record,
    ):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        service.add_cv(sample_cv_data, "old-cv")
        service.repository.add_optimized_cv(
            service.repository.get_job_posting_record("acme-swe"),
            build_optimized_cv_record("opt-1", "acme-swe", "old-cv"),
            CurriculumVitae(**sample_cv_data),
        )
        service.rename_cv("old-cv", "new-cv")
        record = service.repository.get_optimized_cv_record("acme-swe", "opt-1")
        assert record.base_cv_identifier == "new-cv"


class TestGetJobPostings:
    def test_forwards_location_param(self):
        mock_repo = MagicMock()
        mock_repo.get_job_posting_records.return_value = []
        service = ApplicationService(repository=mock_repo)
        service.get_job_postings(location="archived")
        mock_repo.get_job_posting_records.assert_called_once_with(
            location="archived", all=False
        )

    def test_forwards_all_param(self):
        mock_repo = MagicMock()
        mock_repo.get_job_posting_records.return_value = []
        service = ApplicationService(repository=mock_repo)
        service.get_job_postings(all=True)
        mock_repo.get_job_posting_records.assert_called_once_with(
            location=None, all=True
        )


class TestTransitionDocuments:
    @pytest.mark.parametrize(
        "method, arguments, location, path",
        [
            (
                "transition_job_posting",
                ("shortlisted",),
                "shortlisted",
                "job-postings/shortlisted/test-job",
            ),
            ("archive_job_posting", (), "archived", "job-postings/archived/test-job"),
            ("unarchive_job_posting", (), None, "job-postings/test-job"),
            ("mark_applied", ("my-cv",), "applied", "job-postings/applied/test-job"),
        ],
    )
    def test_preserves_moved_document_and_returns_persisted_record(
        self, service, sample_job_posting_data, method, arguments, location, path
    ):
        service.add_job_posting(sample_job_posting_data, "test-job")
        if method == "unarchive_job_posting":
            service.archive_job_posting("test-job")
        content = (
            b"---\ncustom_tag: keep-me\npath: old-path\n---\n# Hand-edited\n\nBody.\n"
        )
        service.add_document("job-postings/test-job/job-posting.md", content)
        result = getattr(service, method)("test-job", *arguments)
        assert result == service.get_job_posting_record("test-job")
        assert result.path == path
        assert result.location == location
        assert service.get_document("job-postings/test-job/job-posting.md") == content


class TestArchiveJobPosting:
    def test_sets_archived_flag(self, service_with_job_posting):
        result = service_with_job_posting.archive_job_posting("acme-swe")
        assert result.is_archived is True
        assert result.location == "archived"
        assert "is_archived" not in result.transitions[-1]


class TestMarkApplied:
    def test_records_application_in_record_and_history(self, service_with_job_posting):
        result = service_with_job_posting.mark_applied("acme-swe", "my-cv")
        assert result.location == "applied"
        assert result.applied_with == "my-cv"
        assert result.applied_at is not None
        assert result.transitions[-1]["applied_with"] == "my-cv"
        assert result.transitions[-1]["applied_at"] == result.applied_at.isoformat()
        assert service_with_job_posting.get_job_posting_record("acme-swe") == result

    def test_records_explicit_applied_at(self, service_with_job_posting):
        from datetime import datetime

        date = datetime(2025, 1, 15)
        result = service_with_job_posting.mark_applied(
            "acme-swe", "my-cv", applied_at=date
        )
        assert result.applied_at == date
        assert result.transitions[-1]["applied_at"] == "2025-01-15T00:00:00"


class TestListingDictionaries:
    @pytest.mark.parametrize(
        "getter, expected_identifier",
        [
            ("get_job_postings", "acme-swe"),
            ("get_cvs", "jane-doe"),
            ("get_optimized_cvs", "opt-1"),
        ],
    )
    def test_returns_json_compatible_dictionaries(
        self,
        service,
        sample_job_posting_data,
        sample_cv_data,
        getter,
        expected_identifier,
        build_optimized_cv_record,
    ):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        service.add_cv(sample_cv_data, "jane-doe")
        service.repository.add_optimized_cv(
            service.repository.get_job_posting_record("acme-swe"),
            build_optimized_cv_record("opt-1", "acme-swe", "jane-doe"),
            CurriculumVitae(**sample_cv_data),
        )

        results = getattr(service, getter)()

        assert len(results) == 1
        assert isinstance(results[0], dict)
        assert results[0]["identifier"] == expected_identifier
        assert isinstance(results[0]["created_at"], str)
        assert isinstance(results[0]["updated_at"], str)
        assert json.loads(json.dumps(results)) == results

    @pytest.mark.parametrize("query", ["ACME", "software", "MID-LEVEL", "example.com"])
    def test_job_posting_keyword_filters(self, service, sample_job_posting_data, query):
        service.add_job_posting(sample_job_posting_data, "acme-swe")

        results = service.get_job_postings(query=query)

        assert [record["identifier"] for record in results] == ["acme-swe"]
        assert service.get_job_postings(query="no match") == []

    def test_job_posting_date_filter(self, service, sample_job_posting_data):
        record = service.add_job_posting(sample_job_posting_data, "acme-swe")

        results = service.get_job_postings(query=record.created_at.date().isoformat())

        assert [item["identifier"] for item in results] == ["acme-swe"]

    @pytest.mark.parametrize("query", ["JANE", "base-cv"])
    def test_cv_keyword_filters(self, service, sample_cv_data, query):
        service.add_cv(sample_cv_data, "base-cv")

        results = service.get_cvs(query=query)

        assert [record["identifier"] for record in results] == ["base-cv"]
        assert service.get_cvs(query="no match") == []


class TestGetOptimizedCvs:
    @pytest.mark.parametrize(
        "file_job_posting",
        [
            lambda service: service.archive_job_posting("acme-swe"),
            lambda service: service.mark_applied("acme-swe", "jane-doe"),
        ],
        ids=["archived", "applied"],
    )
    def test_excludes_optimizations_from_filed_job_postings(
        self,
        service,
        sample_job_posting_data,
        sample_cv_data,
        file_job_posting,
        build_optimized_cv_record,
    ):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        service.add_cv(sample_cv_data, "jane-doe")
        service.repository.add_optimized_cv(
            service.repository.get_job_posting_record("acme-swe"),
            build_optimized_cv_record("opt-1", "acme-swe", "jane-doe"),
            CurriculumVitae(**sample_cv_data),
        )
        file_job_posting(service)
        opts = service.get_optimized_cvs()
        assert not any(o.get("job_posting_identifier") == "acme-swe" for o in opts)

    def test_includes_optimizations_from_active_job_postings(
        self,
        service,
        sample_job_posting_data,
        sample_cv_data,
        build_optimized_cv_record,
    ):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        service.add_cv(sample_cv_data, "jane-doe")
        service.repository.add_optimized_cv(
            service.repository.get_job_posting_record("acme-swe"),
            build_optimized_cv_record("opt-1", "acme-swe", "jane-doe"),
            CurriculumVitae(**sample_cv_data),
        )
        opts = service.get_optimized_cvs()
        assert any(o.get("job_posting_identifier") == "acme-swe" for o in opts)


class TestRemoveOptimizedCv:
    def test_returns_true_when_found(
        self,
        service,
        sample_job_posting_data,
        sample_cv_data,
        build_optimized_cv_record,
    ):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        service.repository.add_optimized_cv(
            service.repository.get_job_posting_record("acme-swe"),
            build_optimized_cv_record("opt-1", "acme-swe", "jane-doe"),
            CurriculumVitae(**sample_cv_data),
        )
        assert service.remove_optimized_cv("acme-swe", "opt-1") is True

    def test_returns_false_when_not_found(self, service, sample_job_posting_data):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        assert service.remove_optimized_cv("acme-swe", "nonexistent") is False

    def test_removes_from_repository(
        self,
        service,
        sample_job_posting_data,
        sample_cv_data,
        build_optimized_cv_record,
    ):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        service.repository.add_optimized_cv(
            service.repository.get_job_posting_record("acme-swe"),
            build_optimized_cv_record("opt-1", "acme-swe", "jane-doe"),
            CurriculumVitae(**sample_cv_data),
        )
        service.remove_optimized_cv("acme-swe", "opt-1")
        assert service.repository.get_optimized_cv_record("acme-swe", "opt-1") is None


class TestRenameOptimizedCv:
    def test_data_accessible_at_new_identifier(
        self,
        service,
        sample_job_posting_data,
        sample_cv_data,
        build_optimized_cv_record,
    ):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        service.repository.add_optimized_cv(
            service.repository.get_job_posting_record("acme-swe"),
            build_optimized_cv_record("opt-1", "acme-swe", "jane-doe"),
            CurriculumVitae(**sample_cv_data),
        )
        service.rename_optimized_cv("acme-swe", "opt-1", "new-id")
        assert service.repository.get_optimized_cv_record("acme-swe", "opt-1") is None
        assert (
            service.repository.get_optimized_cv_record("acme-swe", "new-id") is not None
        )


# ---------------------------------------------------------------------------
# CJ-17 regression tests: service and exporter must use parent stored path
# ---------------------------------------------------------------------------


class TestSaveOptimizedCvUsesParentPath:
    """Optimized CV content and its plan are stored under the parent's current path."""

    def test_saves_to_parent_stored_path(
        self, service, sample_job_posting_data, sample_cv_data, temp_data_dir
    ):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        service.archive_job_posting("acme-swe")

        cv = CurriculumVitae(**sample_cv_data)
        plan = CvTransformationPlan(job_title="Software Engineer", company="Acme Corp")

        service.load(
            "job-postings/acme-swe/cvs/opt-1",
            {
                "curriculum-vitae.json": cv.model_dump(mode="json"),
                "cv-transformation-plan.json": plan.model_dump(mode="json"),
            },
        )
        record = service.get("job-postings/acme-swe/cvs")[0]

        assert record.path == "job-postings/archived/acme-swe/cvs/opt-1"
        uri = "job-postings/acme-swe/cvs/opt-1"
        assert service.get(uri) == cv
        assert (
            json.loads(service.get_document(f"{uri}/cv-transformation-plan.json"))[
                "job_title"
            ]
            == "Software Engineer"
        )


class TestExportOptimizationsUsesParentPath:
    """export('optimizations') must load artifacts and write markdown via the parent's stored path."""

    def test_finds_artifacts_after_parent_path_moved(
        self,
        service,
        sample_job_posting_data,
        sample_cv_data,
        temp_data_dir,
        build_optimized_cv_record,
    ):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        cv = CurriculumVitae(**sample_cv_data)
        plan = CvTransformationPlan(job_title="Software Engineer", company="Acme Corp")

        service.repository.add_optimized_cv(
            service.repository.get_job_posting_record("acme-swe"),
            build_optimized_cv_record("opt-1", "acme-swe", "jane-doe"),
            cv,
        )

        cv_dir = Path(temp_data_dir) / "job-postings/acme-swe/cvs/opt-1"
        plan_data = plan.model_dump(mode="json")
        plan_data["_type"] = "CvTransformationPlan"
        (cv_dir / "cv-transformation-plan.json").write_text(json.dumps(plan_data))

        # Moving the parent carries the nested cvs/ subdir with it.
        service.archive_job_posting("acme-swe")

        count = service.export_markdown(collection_name="optimizations")

        # CV via export_cv counts as 1; plan via load_all_objects counts as 1 more.
        assert count == 2

    def test_markdown_written_at_parent_stored_path(
        self,
        service,
        sample_job_posting_data,
        sample_cv_data,
        temp_data_dir,
        build_optimized_cv_record,
    ):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        cv = CurriculumVitae(**sample_cv_data)
        service.repository.add_optimized_cv(
            service.repository.get_job_posting_record("acme-swe"),
            build_optimized_cv_record("opt-1", "acme-swe", "jane-doe"),
            cv,
        )

        service.archive_job_posting("acme-swe")

        service.export_markdown(collection_name="optimizations")

        cv_md = (
            Path(temp_data_dir)
            / "job-postings/archived/acme-swe/cvs/opt-1/curriculum-vitae.md"
        )
        assert cv_md.exists()


class TestGetCvOptimizationUsesParentPath:
    """get_cv_optimization must load the transformation plan from the parent's stored path."""

    def test_finds_plan_at_parent_stored_path(
        self,
        service,
        sample_job_posting_data,
        sample_cv_data,
        temp_data_dir,
        build_optimized_cv_record,
    ):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        service.archive_job_posting("acme-swe")

        cv = CurriculumVitae(**sample_cv_data)
        plan = CvTransformationPlan(job_title="Software Engineer", company="Acme Corp")

        service.repository.add_optimized_cv(
            service.repository.get_job_posting_record("acme-swe"),
            build_optimized_cv_record("opt-1", "acme-swe", "jane-doe"),
            cv,
        )

        cv_dir = Path(temp_data_dir) / "job-postings/archived/acme-swe/cvs/opt-1"
        plan_json = plan.model_dump(mode="json")
        plan_json["_type"] = "CvTransformationPlan"
        (cv_dir / "cv-transformation-plan.json").write_text(json.dumps(plan_json))

        plan_data, _ = service.get_cv_optimization("acme-swe", "opt-1")

        assert plan_data != {}


class TestObjectExists:
    def test_true_for_existing_job_posting(self, service, sample_job_posting_data):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        assert service.object_exists("job-postings/acme-swe") is True

    def test_true_for_existing_cv(self, service, sample_cv_data):
        service.add_cv(sample_cv_data, "jane-doe")
        assert service.object_exists("cvs/jane-doe") is True

    def test_false_for_missing(self, service):
        assert service.object_exists("cvs/nope") is False

    def test_false_for_unparseable_uri(self, service):
        assert service.object_exists("not a uri") is False

    def test_false_for_document_uri(self, service, sample_cv_data):
        service.add_cv(sample_cv_data, "jane-doe")
        assert service.object_exists("cvs/jane-doe/resume.pdf") is False


class TestUniquifyEntityUri:
    def test_returns_the_uri_when_free(self, service):
        assert service.uniquify_entity_uri("cvs/jane-doe") == "cvs/jane-doe"

    def test_bumps_to_2_on_collision(self, service, sample_cv_data):
        service.add_cv(sample_cv_data, "jane-doe")
        assert service.uniquify_entity_uri("cvs/jane-doe") == "cvs/jane-doe-2"

    def test_bumps_past_existing_suffix(self, service, sample_cv_data):
        service.add_cv(sample_cv_data, "jane-doe")
        service.add_cv(sample_cv_data, "jane-doe-2")
        assert service.uniquify_entity_uri("cvs/jane-doe") == "cvs/jane-doe-3"

    def test_scoped_per_namespace(
        self, service, sample_job_posting_data, sample_cv_data
    ):
        service.add_cv(sample_cv_data, "shared")
        # same identifier in a different namespace does not collide
        assert (
            service.uniquify_entity_uri("job-postings/shared") == "job-postings/shared"
        )


class TestGenerateDefaultEntityUri:
    def test_job_posting_slugifies_company_and_title(
        self, service, sample_job_posting_data
    ):
        assert (
            service.generate_default_entity_uri("job-postings", sample_job_posting_data)
            == "job-postings/acme-corp-software-engineer"
        )

    def test_cv_slugifies_profession(self, service, sample_cv_data):
        assert (
            service.generate_default_entity_uri("cvs", sample_cv_data)
            == "cvs/software-engineer"
        )

    def test_avoids_collision(self, service, sample_cv_data):
        service.add_cv(sample_cv_data, "software-engineer")
        assert (
            service.generate_default_entity_uri("cvs", sample_cv_data)
            == "cvs/software-engineer-2"
        )

    def test_not_specified_company_omitted(self, service):
        data = JobPosting(
            url="https://example.com/job/456",
            company="Not specified",
            title="Developer",
            industry="Tech",
            description="A job",
            experience_level="Senior",
        ).model_dump()
        assert (
            service.generate_default_entity_uri("job-postings", data)
            == "job-postings/developer"
        )

    def test_unrecognized_collection_returns_none(self, service):
        assert service.generate_default_entity_uri("widgets", {}) is None


class TestAddRaisesOnCollision:
    def test_job_posting(self, service, sample_job_posting_data):
        service.add_job_posting(sample_job_posting_data, "acme-swe")
        with pytest.raises(ValueError, match="already exists"):
            service.add_job_posting(sample_job_posting_data, "acme-swe")

    def test_cv(self, service, sample_cv_data):
        service.add_cv(sample_cv_data, "jane-doe")
        with pytest.raises(ValueError, match="already exists"):
            service.add_cv(sample_cv_data, "jane-doe")


@pytest.fixture
def mock_repository_service():
    service = ApplicationService(repository=MagicMock())
    service.markdown_exporter = MagicMock()
    return service


class TestAddJobPostingBuildsRecord:
    def test_builds_unpersisted_record(
        self, mock_repository_service, sample_job_posting_data
    ):
        mock_repository_service.add_job_posting(sample_job_posting_data, "acme-swe")

        record, job_posting = (
            mock_repository_service.repository.add_job_posting.call_args.args
        )
        assert record.identifier == "acme-swe"
        assert record.path is None
        assert record.url == "https://example.com/job/123"
        assert record.company == "Acme Corp"
        assert record.title == "Software Engineer"
        assert record.experience_level == "Mid-level"
        assert record.location is None
        assert record.created_at == record.updated_at
        assert job_posting == JobPosting(**sample_job_posting_data)

    def test_returns_persisted_record(
        self, mock_repository_service, sample_job_posting_data
    ):
        result = mock_repository_service.add_job_posting(
            sample_job_posting_data, "acme-swe"
        )

        persisted = mock_repository_service.repository.add_job_posting.return_value
        assert result is persisted


class TestAddCvBuildsRecord:
    def test_builds_unpersisted_record(self, mock_repository_service, sample_cv_data):
        mock_repository_service.add_cv(sample_cv_data, "jane-doe")

        record, cv = mock_repository_service.repository.add_cv.call_args.args
        assert record.identifier == "jane-doe"
        assert record.path is None
        assert record.name == "Jane Doe"
        assert record.profession == "Software Engineer"
        assert record.created_at == record.updated_at
        assert cv == CurriculumVitae(**sample_cv_data)

    def test_returns_persisted_record(self, mock_repository_service, sample_cv_data):
        result = mock_repository_service.add_cv(sample_cv_data, "jane-doe")

        persisted = mock_repository_service.repository.add_cv.return_value
        assert result is persisted


@pytest.fixture
def service_with_job_posting(service, sample_job_posting_data):
    service.add_job_posting(sample_job_posting_data, "acme-swe")
    return service


class TestTransitionAuditLog:
    def test_sets_location(self, service_with_job_posting):
        record = service_with_job_posting.transition_job_posting(
            "acme-swe", "somewhere"
        )
        assert record.location == "somewhere"
        assert (
            service_with_job_posting.get_job_posting_record("acme-swe").location
            == "somewhere"
        )

    def test_updates_updated_at(self, service_with_job_posting):
        from datetime import datetime

        original = service_with_job_posting.get_job_posting_record("acme-swe")
        now = datetime(2030, 1, 15, 12, 30)
        with patch("services.application.datetime") as clock:
            clock.now.return_value = now
            record = service_with_job_posting.transition_job_posting(
                "acme-swe", "somewhere"
            )
        assert record.updated_at == now
        assert record.created_at == original.created_at
        assert record.transitions[-1]["date"] == "2030-01-15T12:30:00"

    @pytest.mark.parametrize(
        "method, arguments, location, message_location",
        [
            ("transition_job_posting", ("somewhere",), "somewhere", "somewhere"),
            ("transition_job_posting", (".",), None, "."),
            ("transition_job_posting", (None,), None, "None"),
            ("archive_job_posting", (), "archived", "archived"),
            ("unarchive_job_posting", (), None, "."),
            ("mark_applied", ("my-cv",), "applied", "applied"),
        ],
    )
    def test_raises_when_already_in_target_location(
        self, service_with_job_posting, method, arguments, location, message_location
    ):
        service = service_with_job_posting
        if location is not None:
            service.transition_job_posting("acme-swe", location)
        original = service.get_job_posting_record("acme-swe")
        with pytest.raises(ValueError) as error:
            getattr(service, method)("acme-swe", *arguments)
        assert str(error.value) == f"Job posting already in {message_location}"
        assert service.get_job_posting_record("acme-swe") == original

    def test_appends_entry_with_required_keys(self, service_with_job_posting):
        record = service_with_job_posting.transition_job_posting("acme-swe", "applied")
        assert len(record.transitions) == 1
        entry = record.transitions[0]
        assert entry["location"] == "applied"
        assert "date" in entry

    def test_arbitrary_fields_included_in_entry(self, service_with_job_posting):
        record = service_with_job_posting.transition_job_posting(
            "acme-swe",
            "applied",
            {"note": "strong match", "applied_with": "history-only"},
        )
        assert record.transitions[0]["note"] == "strong match"
        assert record.transitions[0]["applied_with"] == "history-only"
        assert record.applied_with is None

    def test_subsequent_transitions_append_not_replace(self, service_with_job_posting):
        service_with_job_posting.transition_job_posting("acme-swe", "applied")
        record = service_with_job_posting.transition_job_posting("acme-swe", "archived")
        assert len(record.transitions) == 2
        assert record.transitions[0]["location"] == "applied"
        assert record.transitions[1]["location"] == "archived"

    def test_dot_stored_verbatim_in_log_normalized_on_record(
        self, service_with_job_posting
    ):
        service_with_job_posting.transition_job_posting("acme-swe", "archived")
        record = service_with_job_posting.transition_job_posting("acme-swe", ".")
        assert record.location is None
        assert record.transitions[-1]["location"] == "."
