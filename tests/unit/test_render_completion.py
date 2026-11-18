import pytest
from click.shell_completion import ShellComplete

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


def _items(service, args, incomplete):
    shell = ShellComplete(main, {"obj": service}, "cv-joint", "_CV_JOINT_COMPLETE")
    return shell.get_completions(list(args), incomplete)


def _values(service, args, incomplete):
    return [item.value for item in _items(service, args, incomplete)]


def test_position1_offers_type_literals(service):
    assert "cv" in _values(service, ["render"], "cv")
    assert "cover-letter" in _values(service, ["render"], "cover")


def test_position1_offers_renderable_cv_uris(service, posting, cv):
    service.add("cvs/my-cv", cv.model_dump())
    service.add("job-postings/acme", posting.model_dump())
    service.add("job-postings/acme/cvs/tailored", cv.model_dump())

    assert _values(service, ["render"], "cvs/") == ["cvs/my-cv"]
    assert _values(service, ["render"], "job") == ["job-postings/acme/cvs/tailored"]


def test_position1_prunes_bare_job_postings(service, posting):
    service.add("job-postings/acme", posting.model_dump())
    assert _values(service, ["render"], "job") == []


def test_position2_file_mode_offers_stdin_and_files(service):
    items = _items(service, ["render", "cv"], "")
    assert "-" in [item.value for item in items]
    assert "file" in [item.type for item in items]


def test_position2_uri_mode_offers_nothing(service):
    assert _items(service, ["render", "cvs/my-cv"], "") == []
