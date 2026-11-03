"""Update contracts through the application and a real repository."""

import pytest

from models import JobPosting
from repositories import FileSystemRepository
from services import ApplicationService


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
        url="https://example.com/old",
        responsibilities=["Old responsibility"],
    )


def test_update_posting_replaces_content_and_refreshes_record(service, posting):
    uri = service.add("job-postings", posting.model_dump(), identifier="acme")
    service.mark_applied("acme", "backend")
    service.add_document(f"{uri}/notes.txt", b"Keep these notes")
    [before] = service.get("job-postings", recursive=True)
    markdown = service.get_document(f"{uri}/job-posting.md")
    replacement = {
        "company": "Globex",
        "title": "Architect",
        "experience_level": "Lead",
        "industry": "Energy",
        "description": "Design tools",
    }

    assert service.update(uri, replacement) == uri

    assert service.get(uri) == JobPosting(**replacement)
    [after] = service.get("job-postings", recursive=True)
    assert (after.company, after.title, after.experience_level, after.url) == (
        "Globex",
        "Architect",
        "Lead",
        None,
    )
    assert after.updated_at > before.updated_at
    summary_fields = {"company", "title", "experience_level", "url", "updated_at"}
    assert after.model_dump(exclude=summary_fields) == before.model_dump(
        exclude=summary_fields
    )
    assert service.get_document(f"{uri}/notes.txt") == b"Keep these notes"
    assert service.get_document(f"{uri}/job-posting.md") == markdown


@pytest.fixture
def cv():
    from models import CurriculumVitae, Contact

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


@pytest.mark.parametrize("collection", ["cvs", "job-postings/acme/cvs"])
def test_update_cv_refreshes_summary_and_preserves_relationships(
    service, posting, cv, collection
):
    service.add("job-postings", posting.model_dump(), identifier="acme")
    service.add("job-postings", posting.model_dump(), identifier="other")
    service.add("cvs", cv.model_dump(), identifier="base")
    service.add_optimized_cv("acme", "backend", "base", cv)
    service.add("job-postings/other/cvs", cv.model_dump(), identifier="backend")
    service.add("cvs", cv.model_dump(), identifier="backend")
    service.archive_job_posting("acme")
    uri = f"{collection}/backend"
    before = next(
        record for record in service.get(collection) if record.identifier == "backend"
    )
    replacement = cv.model_copy(
        update={"name": "Alex Smith", "profession": "Architect"}
    )

    assert service.update(uri, replacement.model_dump_json()) == uri

    assert service.get(uri) == replacement
    after = next(
        record for record in service.get(collection) if record.identifier == "backend"
    )
    assert (after.name, after.profession) == ("Alex Smith", "Architect")
    assert after.updated_at > before.updated_at
    summary_fields = {"name", "profession", "updated_at"}
    assert after.model_dump(exclude=summary_fields) == before.model_dump(
        exclude=summary_fields
    )
    assert service.get("job-postings/other/cvs/backend") == cv


@pytest.mark.parametrize(
    "document_uri",
    [
        "cvs/backend/notes.txt",
        "cvs/backend/curriculum-vitae.json",
        "job-postings/acme/job-posting.json",
        "job-postings/acme/cvs/backend/curriculum-vitae.json",
    ],
)
def test_document_update_is_raw_and_leaves_records_unchanged(
    service, posting, cv, document_uri
):
    service.add("job-postings", posting.model_dump(), identifier="acme")
    service.add("cvs", cv.model_dump(), identifier="backend")
    service.add("job-postings/acme/cvs", cv.model_dump(), identifier="backend")
    service.archive_job_posting("acme")
    service.add_document("cvs/backend/notes.txt", b"old")
    collections = ["job-postings", "cvs", "optimized-cvs"]
    before = [service.get(collection, recursive=True) for collection in collections]
    content = b"\x00\xff\r\nnot JSON\n"

    assert service.update_document(document_uri, content) == document_uri

    assert service.get_document(document_uri) == content
    assert [
        service.get(collection, recursive=True) for collection in collections
    ] == before


def test_update_rejects_a_location_even_when_it_matches_a_posting(service, posting):
    service.add("job-postings", posting.model_dump(), identifier="archived")
    service.add("job-postings", posting.model_dump(), identifier="acme")
    service.archive_job_posting("acme")
    before = service.get("job-postings", recursive=True)

    with pytest.raises(ValueError, match="Cannot update"):
        service.update("job-postings/archived", posting.model_dump())

    assert service.get("job-postings", recursive=True) == before


@pytest.mark.parametrize("source_kind", ["file", "stdin"])
@pytest.mark.parametrize(
    "target",
    [
        "cvs/backend",
        "job-postings/acme",
        "job-postings/acme/cvs/backend",
        "cvs/backend/curriculum-vitae.json",
    ],
)
def test_cli_updates_from_file_or_stdin(
    service, posting, cv, tmp_path, source_kind, target
):
    from click.testing import CliRunner
    from ui.cli import main

    service.add("job-postings", posting.model_dump(), identifier="acme")
    service.add("cvs", cv.model_dump(), identifier="backend")
    service.add("job-postings/acme/cvs", cv.model_dump(), identifier="backend")
    service.archive_job_posting("acme")
    if target.endswith(".json"):
        content = b"\xff\x00\r\n"
    elif target == "job-postings/acme":
        content = (
            posting.model_copy(update={"title": "Architect"}).model_dump_json().encode()
        )
    else:
        content = (
            cv.model_copy(update={"profession": "Architect"}).model_dump_json().encode()
        )
    source = tmp_path / "replacement"
    source.write_bytes(content)

    result = CliRunner(mix_stderr=False).invoke(
        main,
        ["update", target, str(source) if source_kind == "file" else "-"],
        input=content if source_kind == "stdin" else None,
        obj=service,
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == f"{target}\n"
    assert result.stderr == ""
    assert source.read_bytes() == content
    if target.endswith(".json"):
        assert service.get_document(target) == content
    elif target == "job-postings/acme":
        assert service.get(target).title == "Architect"
    else:
        assert service.get(target).profession == "Architect"


@pytest.mark.parametrize("command", ["add", "update"])
def test_cli_validation_error_is_a_short_summary(service, cv, command):
    from click.testing import CliRunner
    from ui.cli import main

    service.add("cvs", cv.model_dump(), identifier="backend")
    arguments = (
        ["add", "cvs", "-", "-i", "other"]
        if command == "add"
        else ["update", "cvs/backend", "-"]
    )
    result = CliRunner(mix_stderr=False).invoke(
        main, arguments, input='{"name": "Alex"}', obj=service
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith(
        "Error: Invalid entity content: contact: Field required"
    )
    assert "errors.pydantic.dev" not in result.stderr
    assert "input_value" not in result.stderr
    assert len(result.stderr.splitlines()) == 1
    assert service.get("cvs/backend") == cv


@pytest.mark.parametrize(
    "data", ["[]", "null", "true", "42", '"text"', "{", {}, {"name": "Incomplete"}]
)
def test_invalid_content_leaves_entity_and_record_unchanged(service, cv, data):
    uri = service.add("cvs", cv.model_dump(), identifier="backend")
    before = service.get("cvs")

    with pytest.raises(ValueError):
        service.update(uri, data)

    assert service.get(uri) == cv
    assert service.get("cvs") == before


@pytest.mark.parametrize(
    "target",
    [
        "cvs",
        "job-postings",
        "job-postings/acme/cvs",
        "optimized-cvs",
        "optimized-cvs/archived",
        "optimized-cvs/backend",
        "cover-letters/backend",
        "cvs/missing",
        "job-postings/missing",
        "job-postings/acme/cvs/missing",
        "cvs/backend/notes.txt",
    ],
)
def test_update_requires_an_existing_writable_entity(service, posting, cv, target):
    service.add("job-postings", posting.model_dump(), identifier="acme")
    service.add("cvs", cv.model_dump(), identifier="backend")
    service.archive_job_posting("acme")
    before = service.get("cvs")

    with pytest.raises(ValueError):
        service.update(target, cv.model_dump())

    assert service.get("cvs/backend") == cv
    assert service.get("cvs") == before


@pytest.mark.parametrize(
    "target",
    [
        "cvs/backend/missing.txt",
        "cvs/missing/notes.txt",
        "cvs/backend/..",
        "cvs/backend/.",
        "cvs/backend",
        "job-postings/acme/cvs",
        "optimized-cvs/backend/notes.txt",
        "cover-letters/backend/notes.txt",
    ],
)
def test_document_update_requires_an_existing_writable_document(service, cv, target):
    service.add("cvs", cv.model_dump(), identifier="backend")
    before = service.list("cvs/backend")

    with pytest.raises((ValueError, OSError)):
        service.update_document(target, b"replacement")

    assert service.list("cvs/backend") == before
    assert service.get("cvs/backend") == cv


@pytest.mark.parametrize(
    "target,content,message",
    [
        ("cvs/backend", b"[]", "Entity content must be a JSON object"),
        ("cvs/backend", b"{", "Expecting property name"),
        ("cvs/backend", b"\xff", "decode"),
        ("cvs/missing", b"{}", "Not found"),
        ("cvs/backend/missing.txt", b"replacement", "No such file"),
        ("optimized-cvs", b"{}", "Cannot update"),
    ],
)
def test_cli_errors_go_to_stderr_without_mutating_content(
    service, cv, target, content, message
):
    from click.testing import CliRunner
    from ui.cli import main

    service.add("cvs", cv.model_dump(), identifier="backend")
    before = service.get("cvs")

    result = CliRunner(mix_stderr=False).invoke(
        main, ["update", target, "-"], input=content, obj=service
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert message in result.stderr
    assert service.get("cvs/backend") == cv
    assert service.get("cvs") == before
