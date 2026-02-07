"""
Unit tests for application service markdown generation.
"""

import pytest
import tempfile
from pathlib import Path

from repositories import FileSystemRepository
from infrastructure import MarkdownWriter
from services import ApplicationService
from models import JobPosting, CurriculumVitae, Contact


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
