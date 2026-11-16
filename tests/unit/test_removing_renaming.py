"""Mutation contracts through public interfaces and a real repository."""

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


def test_remove_document_preserves_entity_and_siblings(service, cv):
    service.add("cvs/backend", cv.model_dump())
    service.add_document("cvs/backend/notes.txt", b"notes")
    service.add_document("cvs/backend/keep.txt", b"keep")

    assert service.remove_document("cvs/backend/notes.txt") == "cvs/backend/notes.txt"

    assert service.list("cvs/backend") == [
        "cvs/backend/curriculum-vitae.json",
        "cvs/backend/keep.txt",
    ]
    assert service.get("cvs/backend") == cv
    assert service.get_document("cvs/backend/keep.txt") == b"keep"
    with pytest.raises(FileNotFoundError):
        service.get_document("cvs/backend/notes.txt")


def test_rename_document_preserves_binary_bytes(service, cv):
    service.add("cvs/backend", cv.model_dump())
    service.add_document("cvs/backend/old.pdf", b"\x00\xff\r\n")

    assert (
        service.rename_document("cvs/backend/old.pdf", "new.pdf")
        == "cvs/backend/new.pdf"
    )

    assert service.get_document("cvs/backend/new.pdf") == b"\x00\xff\r\n"
    assert service.get("cvs/backend") == cv
    assert service.list("cvs/backend") == [
        "cvs/backend/curriculum-vitae.json",
        "cvs/backend/new.pdf",
    ]
    with pytest.raises(FileNotFoundError):
        service.get_document("cvs/backend/old.pdf")


def test_document_rename_collision_preserves_both_documents(service, cv):
    service.add("cvs/backend", cv.model_dump())
    service.add_document("cvs/backend/source.txt", b"source")
    service.add_document("cvs/backend/target.txt", b"target")

    with pytest.raises(ValueError, match="already exists"):
        service.rename_document("cvs/backend/source.txt", "target.txt")

    assert service.get_document("cvs/backend/source.txt") == b"source"
    assert service.get_document("cvs/backend/target.txt") == b"target"


@pytest.mark.parametrize("operation", ["remove", "rename"])
@pytest.mark.parametrize(
    "entity,filename",
    [
        ("cvs/backend", "curriculum-vitae.json"),
        ("job-postings/acme", "job-posting.json"),
        ("job-postings/acme/cvs/backend", "curriculum-vitae.json"),
        ("job-postings/acme", "notes.txt"),
        ("job-postings/acme/cvs/backend", "notes.txt"),
    ],
)
def test_document_mutations_are_raw_and_preserve_records(
    service, posting, cv, operation, entity, filename
):
    service.add("job-postings/acme", posting.model_dump())
    service.add("cvs/backend", cv.model_dump())
    service.add("job-postings/acme/cvs/backend", cv.model_dump())
    service.archive_job_posting("acme")
    if filename == "notes.txt":
        service.add_document(f"{entity}/{filename}", b"\xff\x00notes")
    before = [
        service.get(c, recursive=True) for c in ("job-postings", "cvs", "optimized-cvs")
    ]
    uri = f"{entity}/{filename}"
    original = service.get_document(uri)
    siblings = [u for u in service.list(entity) if u != uri]

    if operation == "remove":
        assert service.remove_document(uri) == uri
        assert service.list(entity) == siblings
    else:
        assert service.rename_document(uri, "renamed.bin") == f"{entity}/renamed.bin"
        assert service.get_document(f"{entity}/renamed.bin") == original
        assert set(service.list(entity)) == {*siblings, f"{entity}/renamed.bin"}

    assert [
        service.get(c, recursive=True) for c in ("job-postings", "cvs", "optimized-cvs")
    ] == before
    with pytest.raises(FileNotFoundError):
        service.get_document(uri)


@pytest.mark.parametrize("operation", ["remove", "rename"])
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
def test_document_mutations_reject_invalid_or_missing_sources(
    service, cv, operation, target
):
    service.add("cvs/backend", cv.model_dump())
    before = service.list("cvs/backend")

    with pytest.raises((ValueError, OSError)):
        if operation == "remove":
            service.remove_document(target)
        else:
            service.rename_document(target, "new.txt")

    assert service.list("cvs/backend") == before
    assert service.get("cvs/backend") == cv


@pytest.mark.parametrize(
    "filename", ["", ".", "..", "../other.txt", "cvs/backend/new.txt"]
)
def test_document_rename_rejects_invalid_destination(service, cv, filename):
    service.add("cvs/backend", cv.model_dump())
    service.add_document("cvs/backend/source.txt", b"source")
    before = service.list("cvs/backend")

    with pytest.raises(ValueError):
        service.rename_document("cvs/backend/source.txt", filename)

    assert service.list("cvs/backend") == before
    assert service.get_document("cvs/backend/source.txt") == b"source"


@pytest.mark.parametrize(
    "uri", ["cvs/backend", "job-postings/acme", "job-postings/acme/cvs/backend"]
)
def test_remove_entity_returns_uri_and_removes_its_documents(service, posting, cv, uri):
    service.add("job-postings/acme", posting.model_dump())
    service.add("cvs/backend", cv.model_dump())
    service.add("job-postings/acme/cvs/backend", cv.model_dump())
    service.archive_job_posting("acme")
    service.add_document(f"{uri}/notes.txt", b"notes")

    assert service.remove(uri) == uri

    with pytest.raises(ValueError, match="Not found"):
        service.get(uri)
    with pytest.raises(ValueError, match="Not found"):
        service.get_document(f"{uri}/notes.txt")
    if uri == "job-postings/acme":
        assert service.get("optimized-cvs", recursive=True) == []
        assert service.get("cvs/backend") == cv
    else:
        assert service.get("job-postings/acme") == posting


@pytest.mark.parametrize(
    "uri,new_uri",
    [
        ("cvs/backend", "cvs/renamed"),
        ("job-postings/acme", "job-postings/renamed"),
        ("job-postings/acme/cvs/backend", "job-postings/acme/cvs/renamed"),
    ],
)
def test_rename_entity_preserves_content_documents_and_relationships(
    service, posting, cv, uri, new_uri
):
    service.add("job-postings/acme", posting.model_dump())
    service.add("cvs/backend", cv.model_dump())
    service.load(
        "job-postings/acme/cvs/backend",
        {"base_cv_uri": "cvs/backend", "curriculum-vitae.json": cv.model_dump()},
    )
    service.archive_job_posting("acme")
    service.add_document(f"{uri}/notes.txt", b"\xffnotes")
    content = service.get(uri)

    assert service.rename(uri, "renamed") == new_uri

    assert service.get(new_uri) == content
    assert service.get_document(f"{new_uri}/notes.txt") == b"\xffnotes"
    with pytest.raises(ValueError, match="Not found"):
        service.get(uri)
    [optimized] = service.get("optimized-cvs", recursive=True)
    assert optimized.base_cv_identifier == (
        "renamed" if uri == "cvs/backend" else "backend"
    )
    assert optimized.job_posting_identifier == (
        "renamed" if uri == "job-postings/acme" else "acme"
    )
    assert (
        service.get(
            "job-postings/renamed/cvs/backend"
            if uri == "job-postings/acme"
            else (new_uri if "/cvs/" in uri else "job-postings/acme/cvs/backend")
        )
        == cv
    )


@pytest.mark.parametrize("operation", ["remove", "rename"])
@pytest.mark.parametrize(
    "target",
    [
        "cvs",
        "job-postings",
        "job-postings/acme/cvs",
        "job-postings/archived",
        "optimized-cvs",
        "optimized-cvs/archived",
        "optimized-cvs/backend",
        "cover-letters/backend",
        "cvs/missing",
        "job-postings/missing",
        "job-postings/acme/cvs/missing",
        "cvs/backend/curriculum-vitae.json",
    ],
)
def test_entity_mutations_require_an_existing_writable_entity(
    service, posting, cv, operation, target
):
    service.add("job-postings/acme", posting.model_dump())
    service.add("job-postings/archived", posting.model_dump())
    service.add("cvs/backend", cv.model_dump())
    service.archive_job_posting("acme")
    before = service.get("job-postings", recursive=True)

    with pytest.raises(ValueError):
        if operation == "remove":
            service.remove(target)
        else:
            service.rename(target, "new")

    assert service.get("cvs/backend") == cv
    assert service.get("job-postings", recursive=True) == before


@pytest.mark.parametrize("collection", ["cvs", "job-postings", "job-postings/acme/cvs"])
def test_entity_rename_collision_preserves_both_entities(
    service, posting, cv, collection
):
    service.add("job-postings/acme", posting.model_dump())
    data = posting.model_dump() if collection == "job-postings" else cv.model_dump()
    service.add(f"{collection}/source", data)
    service.add(f"{collection}/target", data)
    before = service.get(collection)

    with pytest.raises(ValueError, match="already exists"):
        service.rename(f"{collection}/source", "target")

    assert service.get(collection) == before
    assert service.get(f"{collection}/source").model_dump() == data
    assert service.get(f"{collection}/target").model_dump() == data


@pytest.mark.parametrize(
    "target",
    [
        "cvs/backend",
        "job-postings/acme",
        "job-postings/acme/cvs/backend",
        "cvs/backend/notes.txt",
        "job-postings/acme/job-posting.json",
        "job-postings/acme/cvs/backend/curriculum-vitae.json",
    ],
)
def test_cli_remove_prints_only_affected_uri(service, posting, cv, target):
    from click.testing import CliRunner
    from ui.cli import main

    service.add("job-postings/acme", posting.model_dump())
    service.add("cvs/backend", cv.model_dump())
    service.add("job-postings/acme/cvs/backend", cv.model_dump())
    service.add_document("cvs/backend/notes.txt", b"notes")
    service.archive_job_posting("acme")

    result = CliRunner(mix_stderr=False).invoke(main, ["remove", target], obj=service)

    assert result.exit_code == 0, result.output
    assert result.stdout == f"{target}\n"
    assert result.stderr == ""
    if target.endswith((".txt", ".json")):
        with pytest.raises(FileNotFoundError):
            service.get_document(target)
    else:
        with pytest.raises(ValueError, match="Not found"):
            service.get(target)


def test_cli_document_rename_prints_new_uri(service, cv):
    from click.testing import CliRunner
    from ui.cli import main

    service.add("cvs/backend", cv.model_dump())
    service.add_document("cvs/backend/notes.txt", b"\xffnotes")

    result = CliRunner(mix_stderr=False).invoke(
        main, ["rename", "cvs/backend/notes.txt", "new notes.txt"], obj=service
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == "cvs/backend/new notes.txt\n"
    assert result.stderr == ""
    assert service.get_document("cvs/backend/new notes.txt") == b"\xffnotes"
    with pytest.raises(FileNotFoundError):
        service.get_document("cvs/backend/notes.txt")


@pytest.mark.parametrize(
    "uri,new_uri",
    [
        ("cvs/backend", "cvs/renamed"),
        ("job-postings/acme", "job-postings/renamed"),
        ("job-postings/acme/cvs/backend", "job-postings/acme/cvs/renamed"),
    ],
)
@pytest.mark.parametrize("full_uri", [False, True])
def test_cli_entity_rename_accepts_bare_name_or_matching_uri(
    service, posting, cv, uri, new_uri, full_uri
):
    from click.testing import CliRunner
    from ui.cli import main

    service.add("job-postings/acme", posting.model_dump())
    service.add("cvs/backend", cv.model_dump())
    service.add("job-postings/acme/cvs/backend", cv.model_dump())
    service.archive_job_posting("acme")
    content = service.get(uri)

    result = CliRunner(mix_stderr=False).invoke(
        main, ["rename", uri, new_uri if full_uri else "renamed"], obj=service
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == f"{new_uri}\n"
    assert result.stderr == ""
    assert service.get(new_uri) == content
    with pytest.raises(ValueError, match="Not found"):
        service.get(uri)


@pytest.mark.parametrize(
    "arguments,message",
    [
        (["remove", "cvs/missing"], "Not found"),
        (["remove", "cvs/backend/missing.txt"], "No such file"),
        (["remove", "optimized-cvs"], "Cannot remove"),
        (["rename", "cvs/missing", "new"], "Not found"),
        (["rename", "cvs/backend/missing.txt", "new.txt"], "No such file"),
        (
            ["rename", "cvs/backend/notes.txt", "curriculum-vitae.json"],
            "already exists",
        ),
        (["rename", "cvs/backend/notes.txt", "../new.txt"], "illegal filename"),
        (["rename", "cvs/backend", "job-postings/new"], "illegal identifier"),
        (["rename", "cvs/backend", "bad name"], "illegal identifier"),
    ],
)
def test_cli_mutation_errors_preserve_data_and_report_on_stderr(
    service, cv, arguments, message
):
    from click.testing import CliRunner
    from ui.cli import main

    service.add("cvs/backend", cv.model_dump())
    service.add_document("cvs/backend/notes.txt", b"notes")
    before = service.get("cvs")

    result = CliRunner(mix_stderr=False).invoke(main, arguments, obj=service)

    assert result.exit_code != 0
    assert result.stdout == ""
    assert message in result.stderr
    assert service.get("cvs") == before
    assert service.get("cvs/backend") == cv
    assert service.get_document("cvs/backend/notes.txt") == b"notes"


@pytest.mark.parametrize("command", ["remove", "rename"])
def test_mutation_completion_offers_documents_at_canonical_addresses(
    service, posting, cv, command
):
    import click
    from ui.cli import main

    service.add("job-postings/acme", posting.model_dump())
    service.add("job-postings/acme/cvs/backend", cv.model_dump())
    service.add_document("job-postings/acme/cvs/backend/notes.txt", b"notes")
    service.archive_job_posting("acme")
    prefix = "job-postings/acme/cvs/backend/"
    expected = [f"{prefix}curriculum-vitae.json", f"{prefix}notes.txt"]
    assert service.complete_targets(prefix) == expected

    cmd = main.commands[command]
    ctx = click.Context(cmd, obj=service)
    argument = next(p for p in cmd.params if p.name == "uri")
    assert [item.value for item in argument.shell_complete(ctx, prefix)] == expected


def test_document_rename_cannot_take_a_child_collection_address(service, posting):
    service.add("job-postings/acme", posting.model_dump())
    service.add_document("job-postings/acme/notes.txt", b"notes")

    with pytest.raises(ValueError, match="document"):
        service.rename_document("job-postings/acme/notes.txt", "cvs")

    assert service.get_document("job-postings/acme/notes.txt") == b"notes"
    assert service.list("job-postings/acme/cvs") == []
