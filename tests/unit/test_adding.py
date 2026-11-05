"""Adding contracts through the application and a real repository."""

import pytest
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


def test_adding_a_cv_uri_creates_that_base_cv(service, cv):
    uri = service.add("cvs/backend", cv.model_dump())

    assert uri == "cvs/backend"
    assert service.get(uri) == cv


def test_adding_to_job_postings_creates_a_posting(service, posting):
    uri = service.add("job-postings/acme", posting.model_dump())

    assert uri == "job-postings/acme"
    assert service.get(uri) == posting


def test_adding_to_a_postings_cvs_creates_an_optimized_cv(service, posting, cv):
    service.add("job-postings/acme", posting.model_dump())

    uri = service.add("job-postings/acme/cvs/backend", cv.model_dump())

    assert uri == "job-postings/acme/cvs/backend"
    assert service.get(uri) == cv
    [record] = service.get("job-postings/acme/cvs")
    assert record.job_posting_identifier == "acme"
    assert record.base_cv_identifier is None


@pytest.mark.parametrize(
    "target",
    [
        "optimized-cvs/backend",
        "optimized-cvs/applied/backend",
        "cover-letters/backend",
        "nowhere/backend",
    ],
)
def test_adding_outside_a_writable_collection_fails(service, cv, target):
    with pytest.raises(ValueError, match=f"Cannot add to {target}"):
        service.add(target, cv.model_dump())

    assert service.list("cvs") == []


def test_adding_an_existing_identifier_is_a_collision(service, posting, cv):
    for identifier in ("acme", "globex"):
        service.add(f"job-postings/{identifier}", posting.model_dump())
    service.add("cvs/backend", cv.model_dump())
    service.add("job-postings/acme/cvs/backend", cv.model_dump())
    renamed = cv.model_copy(update={"name": "Someone Else"}).model_dump()

    for collection in ("cvs", "job-postings/acme/cvs"):
        with pytest.raises(ValueError, match=f"^Already exists: {collection}/backend$"):
            service.add(f"{collection}/backend", renamed)
        assert service.get(f"{collection}/backend") == cv

    assert service.add("job-postings/globex/cvs/backend", renamed) == (
        "job-postings/globex/cvs/backend"
    )


@pytest.mark.parametrize("identifier", [" ", "back end"])
def test_adding_requires_a_valid_identifier(service, cv, identifier):
    with pytest.raises(ValueError, match="illegal identifier"):
        service.add(f"cvs/{identifier}", cv.model_dump())

    assert service.list("cvs") == []


def test_adding_an_optimized_cv_requires_an_existing_posting(service, cv):
    with pytest.raises(ValueError, match="Not found"):
        service.add("job-postings/missing/cvs/backend", cv.model_dump())

    assert service.list("optimized-cvs", recursive=True) == []


def test_adding_accepts_json_text(service, cv):
    uri = service.add("cvs/backend", cv.model_dump_json())

    assert service.get(uri) == cv


@pytest.mark.parametrize("data", ["[]", "null", '"text"', "42", "true"])
def test_adding_requires_a_json_object(service, data):
    with pytest.raises(ValueError, match="^Entity content must be a JSON object$"):
        service.add("cvs/backend", data)

    assert service.list("cvs") == []


def test_document_addition_preserves_binary_bytes(service, cv):
    service.add_cv(cv.model_dump(), "backend")
    content = b"%PDF-1.7\r\n\x00\xff\xfe\n"

    uri = service.add_document("cvs/backend/application.pdf", content)

    assert uri == "cvs/backend/application.pdf"
    assert service.get_document(uri) == content


def test_document_addition_requires_an_existing_entity(service):
    with pytest.raises(ValueError, match="Not found"):
        service.add_document("cvs/missing/notes.md", b"# Notes\n")


@pytest.mark.parametrize("target", ["cvs/backend/..", "cvs/backend/."])
def test_document_addition_requires_a_valid_filename(service, cv, tmp_path, target):
    service.add("cvs/backend", cv.model_dump())
    before = sorted(tmp_path.rglob("*"))

    with pytest.raises(ValueError, match="illegal filename"):
        service.add_document(target, b"x")

    assert sorted(tmp_path.rglob("*")) == before


@pytest.mark.parametrize(
    "target",
    [
        "job-postings/acme/cvs",
        "job-postings/acme",
        "cvs",
        "cvs/backend/../../escape.txt",
    ],
)
def test_document_addition_requires_a_document_uri(
    service, posting, cv, tmp_path, target
):
    service.add("job-postings/acme", posting.model_dump())
    before = sorted(tmp_path.rglob("*"))

    with pytest.raises(ValueError, match=f"^{target} is not a document address$"):
        service.add_document(target, b"x")

    assert sorted(tmp_path.rglob("*")) == before


def test_existing_document_is_a_collision_named_by_logical_uri(service, posting):
    service.add_job_posting(posting.model_dump(), "acme")
    service.archive_job_posting("acme")
    service.add_document("job-postings/acme/notes.md", b"# Notes\n")

    with pytest.raises(
        ValueError, match="^Document already exists: job-postings/acme/notes.md$"
    ):
        service.add_document("job-postings/acme/notes.md", b"# Overwrite\n")
    assert service.get_document("job-postings/acme/notes.md") == b"# Notes\n"


def test_cli_adds_an_entity_and_prints_only_its_uri(service, cv, tmp_path):
    source = tmp_path / "cv.json"
    source.write_text(cv.model_dump_json())

    result = CliRunner().invoke(main, ["add", "cvs/backend", str(source)], obj=service)

    assert result.exit_code == 0, result.output
    assert result.stdout == "cvs/backend\n"
    assert service.get("cvs/backend") == cv


@pytest.mark.parametrize(
    "target, expected",
    [
        ("cvs/backend/", "cvs/backend/export.pdf"),
        ("cvs/backend/application.pdf", "cvs/backend/application.pdf"),
    ],
)
def test_cli_attaches_a_document_byte_for_byte(service, cv, tmp_path, target, expected):
    service.add("cvs/backend", cv.model_dump())
    source = tmp_path / "export.pdf"
    source.write_bytes(b"%PDF-1.7\r\n\x00\xff\xfe\n")

    result = CliRunner().invoke(main, ["add", target, str(source)], obj=service)

    assert result.exit_code == 0, result.output
    assert result.stdout == f"{expected}\n"
    assert service.get_document(expected) == source.read_bytes()


def test_cli_rejects_a_document_named_after_a_child_collection(
    service, posting, tmp_path
):
    service.add("job-postings/acme", posting.model_dump())
    source = tmp_path / "cvs"
    source.write_bytes(b"x")

    result = CliRunner(mix_stderr=False).invoke(
        main, ["add", "job-postings/acme/", str(source)], obj=service
    )

    assert result.exit_code == 1
    assert result.stdout_bytes == b""
    assert result.stderr == "Error: job-postings/acme/cvs is not a document address\n"


def test_cli_adds_an_entity_from_stdin(service, posting, cv):
    service.add("job-postings/acme", posting.model_dump())

    result = CliRunner().invoke(
        main,
        ["add", "job-postings/acme/cvs/backend", "-"],
        input=cv.model_dump_json(),
        obj=service,
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == "job-postings/acme/cvs/backend\n"
    assert service.get("job-postings/acme/cvs/backend") == cv


@pytest.mark.parametrize(
    "target, message",
    [
        ("cvs", "Cannot add to cvs"),
        ("job-postings/acme/cvs", "Cannot add to job-postings/acme/cvs"),
        ("cvs/", "cvs/cv.json is not a document address"),
        ("optimized-cvs/other", "Cannot add to optimized-cvs/other"),
        ("cvs/backend", "Already exists: cvs/backend"),
        ("cvs/back end", "illegal identifier"),
        ("cvs/missing/", "Not found"),
        ("cvs/backend/cv.json", "Document already exists: cvs/backend/cv.json"),
    ],
)
def test_cli_add_reports_errors_on_stderr(service, cv, tmp_path, target, message):
    service.add("cvs/backend", cv.model_dump())
    service.add_document("cvs/backend/cv.json", b"{}")
    source = tmp_path / "cv.json"
    source.write_text(cv.model_dump_json())

    result = CliRunner(mix_stderr=False).invoke(
        main, ["add", target, str(source)], obj=service
    )

    assert result.exit_code != 0
    assert result.stdout_bytes == b""
    assert f"Error: {message}" in result.stderr


def test_cli_reports_non_object_entity_content_on_stderr(service):
    result = CliRunner(mix_stderr=False).invoke(
        main, ["add", "cvs/backend", "-"], input="[]", obj=service
    )

    assert result.exit_code == 1
    assert result.stdout_bytes == b""
    assert result.stderr == "Error: Entity content must be a JSON object\n"
    assert service.list("cvs") == []


def test_cli_stdin_document_needs_a_document_uri(service, cv):
    service.add("cvs/backend", cv.model_dump())

    result = CliRunner(mix_stderr=False).invoke(
        main, ["add", "cvs/backend/", "-"], input="# Notes\n", obj=service
    )

    assert result.exit_code != 0
    assert "Error: stdin needs a document URI" in result.stderr
    assert "cvs/backend/-" not in service.list("cvs/backend")
