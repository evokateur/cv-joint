"""URI parsing and record resolution."""

import pytest

from models import JobPosting, CurriculumVitae, CoverLetter
from repositories import FileSystemRepository

from services.addressing import parse_uri, resolve_record


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


@pytest.fixture
def repository(tmp_path):
    return FileSystemRepository(data_dir=str(tmp_path))


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


class TestResolveRecord:
    def test_resolves_job_posting(self, repository, sample_job_posting):
        from models import JobPostingRecord

        repository.add_job_posting(sample_job_posting, "acme-swe")
        record = resolve_record(repository, "job-postings/acme-swe")
        assert isinstance(record, JobPostingRecord)
        assert record.identifier == "acme-swe"

    def test_resolves_cv(self, repository, sample_cv):
        from models import CurriculumVitaeRecord

        repository.add_cv(sample_cv, "jane-doe")
        record = resolve_record(repository, "cvs/jane-doe")
        assert isinstance(record, CurriculumVitaeRecord)
        assert record.identifier == "jane-doe"

    def test_resolves_optimized_cv(self, repository, sample_job_posting, sample_cv):
        from models import OptimizedCvRecord

        repository.add_job_posting(sample_job_posting, "acme-swe")
        repository.add_optimized_cv("acme-swe", "jane-v2", "jane-doe", sample_cv)
        record = resolve_record(repository, "job-postings/acme-swe/cvs/jane-v2")
        assert isinstance(record, OptimizedCvRecord)
        assert record.identifier == "jane-v2"

    def test_resolves_cover_letter(self, repository, sample_cover_letter):
        from models import CoverLetterRecord

        repository.add_cover_letter(sample_cover_letter, "frobozzco-magic-gunk")
        record = resolve_record(repository, "cover-letters/frobozzco-magic-gunk")
        assert isinstance(record, CoverLetterRecord)
        assert record.identifier == "frobozzco-magic-gunk"

    def test_raises_when_not_found(self, repository):
        with pytest.raises(ValueError, match="Not found"):
            resolve_record(repository, "job-postings/nonexistent")
