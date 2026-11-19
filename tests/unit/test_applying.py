"""Applying to a posting through the CLI, the application and a real repository."""

from datetime import datetime

import pytest
from click.shell_completion import ShellComplete
from click.testing import CliRunner

from models import Contact, CurriculumVitae, JobPosting
from repositories import FileSystemRepository
from services import ApplicationService
from ui.cli import main


@pytest.fixture
def service(tmp_path):
    return ApplicationService(repository=FileSystemRepository(str(tmp_path)))


@pytest.fixture
def posting():
    return JobPosting(
        company="Acme",
        title="Engineer",
        experience_level="Senior",
        industry="Software",
        description="Build tools",
    )


@pytest.fixture
def cv():
    return CurriculumVitae(
        name="Jane Doe",
        profession="Engineer",
        contact=Contact(
            city="Oakland", state="CA", email="jane@example.com", phone="555-1234"
        ),
        core_expertise=[],
        qualifications=[],
        education=[],
        experience=[],
        additional_experience=[],
        areas_of_expertise=[],
        languages=[],
    )


def test_apply_completed_optimized_cv_preserves_posting_reference(service, posting, cv):
    service.add("job-postings/acme", posting.model_dump())
    service.add("job-postings/acme/cvs/backend", cv.model_dump())
    shell = ShellComplete(main, {"obj": service}, "cv-joint", "_CV_JOINT_COMPLETE")
    candidate = shell.get_completions(["apply", "job-postings/acme"], "job")[0].value
    result = CliRunner().invoke(
        main, ["apply", "job-postings/acme", candidate], obj=service
    )
    assert result.exit_code == 0, result.output
    assert service.get("job-postings/applied")[0].applied_with == "acme/backend"


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("missing", "missing"),
        ("acme/missing", "acme/missing"),
        ("cvs/missing", "missing"),
        ("job-postings/acme/cvs/missing", "acme/missing"),
    ],
)
def test_apply_normalizes_unvalidated_references(service, posting, reference, expected):
    service.add("job-postings/acme", posting.model_dump())
    result = CliRunner().invoke(
        main,
        ["apply", "job-postings/acme", reference, "--date", "2025-01-15"],
        obj=service,
    )
    assert result.exit_code == 0, result.output
    record = service.get("job-postings/applied")[0]
    assert record.applied_with == expected
    assert record.applied_at == datetime(2025, 1, 15)
    assert result.output == f"Marked job-postings/acme as applied with {expected}\n"


def test_apply_without_date_records_the_current_time(service, posting):
    service.add("job-postings/acme", posting.model_dump())
    before = datetime.now()
    result = CliRunner().invoke(
        main, ["apply", "job-postings/acme", "cvs/backend"], obj=service
    )
    after = datetime.now()
    assert result.exit_code == 0, result.output
    assert before <= service.get("job-postings/applied")[0].applied_at <= after


def test_apply_rejects_non_posting_uri(service):
    result = CliRunner().invoke(main, ["apply", "cvs/backend", "backend"], obj=service)
    assert result.exit_code == 2
    assert "unrecognised URI 'cvs/backend'" in result.output
    assert "Expected: job-postings/{id}" in result.output
