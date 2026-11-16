"""Cover letters through the public application and CLI with real storage."""

import json

import pytest
import yaml
from click.testing import CliRunner
from click.shell_completion import ShellComplete

from models import CoverLetter
from repositories import FileSystemRepository
from services import ApplicationService
from ui.cli import main


@pytest.fixture
def service(tmp_path):
    return ApplicationService(repository=FileSystemRepository(str(tmp_path)))


@pytest.fixture
def letter():
    return CoverLetter(
        name="Jane Doe",
        contact={
            "city": "Oakland",
            "state": "CA",
            "email": "jane@example.com",
            "phone": "555-1234",
        },
        company="Acme",
        position="Engineer",
        salutation="Dear hiring team,",
        paragraphs=["I build reliable tools.", "I would welcome a conversation."],
        closing="Sincerely,",
    )


def test_added_cover_letter_can_be_read_after_reopening(service, letter, tmp_path):
    assert service.add("cover-letters/jane-acme", letter.model_dump()) == (
        "cover-letters/jane-acme"
    )

    reopened = ApplicationService(repository=FileSystemRepository(str(tmp_path)))
    assert reopened.get("cover-letters/jane-acme") == letter


def test_cover_letter_collection_selects_records_and_lists_documents(service, letter):
    assert service.get("cover-letters") == []
    assert service.list("cover-letters") == []

    service.add("cover-letters/jane-acme", letter.model_dump_json())
    service.add(
        "cover-letters/draft", letter.model_copy(update={"company": None}).model_dump()
    )

    [record] = service.get("cover-letters", query="ACME", recursive=True)
    assert (record.identifier, record.name, record.company, record.position) == (
        "jane-acme",
        "Jane Doe",
        "Acme",
        "Engineer",
    )
    assert record.created_at == record.updated_at
    assert service.list("cover-letters", query="ACME") == ["cover-letters/jane-acme"]
    assert service.list("cover-letters", query="missing") == []
    assert service.list("cover-letters/jane-acme", query="ignored") == [
        "cover-letters/jane-acme/cover-letter.json"
    ]
    assert service.get("cover-letters/jane-acme", query="ignored") == letter


def test_cover_letter_documents_preserve_bytes_through_mutations(service, letter):
    uri = service.add("cover-letters/jane-acme", letter.model_dump())
    document = f"{uri}/application.pdf"
    assert service.add_document(document, b"%PDF\x00\xff") == document
    assert service.get_document(document) == b"%PDF\x00\xff"
    assert document in service.list(uri)
    assert service.update_document(document, b"%PDF\x00\xfe") == document
    renamed = f"{uri}/final application.pdf"
    assert service.rename_document(document, "final application.pdf") == renamed
    assert service.get_document(renamed) == b"%PDF\x00\xfe"
    assert document not in service.list(uri)
    assert service.remove_document(renamed) == renamed
    assert renamed not in service.list(uri)
    assert service.get(uri) == letter


def test_updating_cover_letter_refreshes_summary_and_preserves_identity(
    service, letter, tmp_path
):
    uri = service.add("cover-letters/jane-acme", letter.model_dump())
    service.add_document(f"{uri}/notes.md", b"Keep my notes")
    [before] = service.get("cover-letters")
    replacement = letter.model_copy(
        update={
            "name": "Janet Doe",
            "company": None,
            "position": "Lead",
            "paragraphs": ["A new letter."],
        }
    )

    assert service.update(uri, replacement.model_dump_json()) == uri

    reopened = ApplicationService(repository=FileSystemRepository(str(tmp_path)))
    assert reopened.get(uri) == replacement
    [after] = reopened.get("cover-letters")
    assert (after.name, after.company, after.position) == ("Janet Doe", None, "Lead")
    assert (after.identifier, after.path, after.created_at) == (
        before.identifier,
        before.path,
        before.created_at,
    )
    assert after.updated_at > before.updated_at
    assert reopened.get_document(f"{uri}/notes.md") == b"Keep my notes"


def test_renaming_cover_letter_preserves_content_and_documents(service, letter):
    uri = service.add("cover-letters/draft", letter.model_dump())
    service.add_document(f"{uri}/notes.md", b"Keep my notes")
    [before] = service.get("cover-letters")

    assert service.rename(uri, "final") == "cover-letters/final"

    assert service.list("cover-letters") == ["cover-letters/final"]
    assert service.get("cover-letters/final") == letter
    assert service.get_document("cover-letters/final/notes.md") == b"Keep my notes"
    [after] = service.get("cover-letters")
    assert after.created_at == before.created_at
    with pytest.raises(ValueError, match="Not found"):
        service.get(uri)


def test_removing_cover_letter_removes_its_documents(service, letter):
    uri = service.add("cover-letters/draft", letter.model_dump())
    service.add_document(f"{uri}/notes.md", b"Old notes")

    assert service.remove(uri) == uri

    assert service.list("cover-letters") == []
    with pytest.raises(ValueError, match="Not found"):
        service.get(uri)
    service.add(uri, letter.model_dump())
    assert service.list(uri) == [f"{uri}/cover-letter.json"]


@pytest.mark.parametrize("collection", ["cover-letters", None])
def test_export_cover_letter_writes_readable_markdown_with_record_metadata(
    service, letter, collection
):
    uri = service.add("cover-letters/jane-acme", letter.model_dump())

    assert service.export_markdown(collection) == 1

    markdown = service.get_document(f"{uri}/cover-letter.md").decode()
    _, frontmatter, body = markdown.split("---\n", 2)
    assert yaml.safe_load(frontmatter)["identifier"] == "jane-acme"
    assert "# Jane Doe" in body
    assert "jane@example.com" in body
    assert "Acme" in body and "Engineer" in body
    assert (
        "Dear hiring team,\n\nI build reliable tools.\n\nI would welcome a conversation.\n\nSincerely,"
        in body
    )


def test_cli_renders_stored_cover_letter_to_tex(service, letter):
    uri = service.add("cover-letters/jane-acme", letter.model_dump())

    result = CliRunner().invoke(
        main, ["render", uri, "-f", "tex", "-o", "-"], obj=service
    )

    assert result.exit_code == 0, result.output
    assert "Cover Letter - Jane Doe" in result.output
    assert "Dear hiring team," in result.output
    assert "I build reliable tools." in result.output


def test_completion_offers_cover_letter_targets_and_add_destinations(service, letter):
    uri = service.add("cover-letters/jane-acme", letter.model_dump())
    service.add_document(f"{uri}/notes.md", b"Notes")

    assert service.complete_targets("cover") == [
        "cover-letters",
        uri,
        f"{uri}/cover-letter.json",
        f"{uri}/notes.md",
    ]
    assert service.complete_add_destinations("cover") == ["cover-letters/", f"{uri}/"]
    shell = ShellComplete(main, {"obj": service}, "cv-joint", "_CV_JOINT_COMPLETE")
    for command in ("get", "list", "update", "remove", "rename"):
        assert f"{uri}/notes.md" in [
            item.value for item in shell.get_completions([command], "cover")
        ]
    assert [item.value for item in shell.get_completions(["add"], "cover")] == [
        "cover-letters/",
        f"{uri}/",
    ]


def test_render_completion_offers_stored_cover_letters(service, letter):
    service.add("cover-letters/jane-acme", letter.model_dump())

    assert service.complete_render_targets("cover") == ["cover-letters/jane-acme"]
    shell = ShellComplete(main, {"obj": service}, "cv-joint", "_CV_JOINT_COMPLETE")
    assert [item.value for item in shell.get_completions(["render"], "cover")] == [
        "cover-letter",
        "cover-letters/jane-acme",
    ]


def test_cli_cover_letter_entity_round_trip(service, letter, tmp_path):
    runner = CliRunner()
    uri = "cover-letters/draft"
    source = tmp_path / "letter.json"
    source.write_text(letter.model_dump_json())
    added = runner.invoke(main, ["add", uri, str(source)], obj=service)
    assert added.exit_code == 0, added.output
    assert added.stdout == f"{uri}\n"
    fetched = runner.invoke(main, ["get", uri], obj=service)
    assert json.loads(fetched.stdout) == letter.model_dump()
    collection = runner.invoke(
        main, ["get", "cover-letters", "-q", "ACME"], obj=service
    )
    assert [
        json.loads(line)["identifier"] for line in collection.stdout.splitlines()
    ] == ["draft"]
    listed = runner.invoke(main, ["list", "cover-letters"], obj=service)
    assert listed.stdout == f"{uri}\n"
    replacement = letter.model_copy(update={"paragraphs": ["Updated letter."]})
    updated = runner.invoke(
        main, ["update", uri, "-"], input=replacement.model_dump_json(), obj=service
    )
    assert updated.exit_code == 0, updated.output
    assert updated.stdout == f"{uri}\n"
    assert service.get(uri) == replacement
    renamed = runner.invoke(main, ["rename", uri, "cover-letters/final"], obj=service)
    assert renamed.exit_code == 0, renamed.output
    assert renamed.stdout == "cover-letters/final\n"
    removed = runner.invoke(main, ["remove", "cover-letters/final"], obj=service)
    assert removed.exit_code == 0, removed.output
    assert removed.stdout == "cover-letters/final\n"
    assert service.list("cover-letters") == []


@pytest.mark.parametrize("attachment", ["filename", "trailing-slash"])
def test_cli_cover_letter_document_round_trip(service, letter, tmp_path, attachment):
    runner = CliRunner()
    uri = "cover-letters/draft"
    added = runner.invoke(
        main, ["add", uri, "-"], input=letter.model_dump_json(), obj=service
    )
    assert added.exit_code == 0, added.output
    source = tmp_path / "attachment.pdf"
    source.write_bytes(b"%PDF\x00\xff")
    document = f"{uri}/attachment.pdf"
    target = f"{uri}/" if attachment == "trailing-slash" else document
    attached = runner.invoke(main, ["add", target, str(source)], obj=service)
    assert attached.exit_code == 0, attached.output
    assert attached.stdout == f"{document}\n"
    assert source.read_bytes() == b"%PDF\x00\xff"
    fetched = runner.invoke(main, ["get", document], obj=service)
    assert fetched.stdout_bytes == b"%PDF\x00\xff"
    updated = runner.invoke(
        main, ["update", document, "-"], input=b"%PDF\x00\xfe", obj=service
    )
    assert updated.exit_code == 0, updated.output
    renamed = runner.invoke(main, ["rename", document, "final.pdf"], obj=service)
    assert renamed.exit_code == 0, renamed.output
    assert renamed.stdout == f"{uri}/final.pdf\n"
    assert service.get_document(f"{uri}/final.pdf") == b"%PDF\x00\xfe"
    removed = runner.invoke(main, ["remove", f"{uri}/final.pdf"], obj=service)
    assert removed.exit_code == 0, removed.output
    assert removed.stdout == f"{uri}/final.pdf\n"
    assert service.list(uri) == [f"{uri}/cover-letter.json"]


@pytest.mark.parametrize("operation", ["add", "rename"])
def test_cover_letter_collisions_preserve_both_letters(service, letter, operation):
    first = service.add("cover-letters/first", letter.model_dump())
    second_letter = letter.model_copy(update={"name": "Someone Else"})
    second = service.add("cover-letters/second", second_letter.model_dump())

    with pytest.raises(ValueError, match="exists"):
        if operation == "add":
            service.add(second, letter.model_dump())
        else:
            service.rename(first, "second")

    assert service.get(first) == letter
    assert service.get(second) == second_letter


@pytest.mark.parametrize("content", ["{", "[]", '{"name": "Incomplete"}'])
def test_invalid_cover_letter_content_does_not_replace_stored_content(
    service, letter, content
):
    uri = service.add("cover-letters/draft", letter.model_dump())
    before = service.get("cover-letters")

    with pytest.raises(ValueError):
        service.update(uri, content)
    with pytest.raises(ValueError):
        service.add("cover-letters/invalid", content)

    assert service.get(uri) == letter
    assert service.get("cover-letters") == before


@pytest.mark.parametrize(
    "target", ["cover-letters", "cover-letters/", "cover-letters/bad id"]
)
def test_cli_rejects_invalid_cover_letter_destinations(service, letter, target):
    result = CliRunner(mix_stderr=False).invoke(
        main, ["add", target, "-"], input=letter.model_dump_json(), obj=service
    )
    assert result.exit_code != 0
    assert result.stdout == ""
    assert service.list("cover-letters") == []


def test_primary_cover_letter_document_mutations_are_raw(service, letter):
    uri = service.add("cover-letters/draft", letter.model_dump())
    before = service.get("cover-letters")
    primary = f"{uri}/cover-letter.json"
    service.update_document(primary, b"\x00\xff")
    assert service.get_document(primary) == b"\x00\xff"
    renamed = service.rename_document(primary, "original.bin")
    assert service.get_document(renamed) == b"\x00\xff"
    service.remove_document(renamed)
    assert service.list(uri) == []
    assert service.get("cover-letters") == before


def test_cli_exports_cover_letters_from_configured_repository(
    service, letter, tmp_path, monkeypatch
):
    from config import root

    settings = root.get_settings()
    settings.repositories.filesystem.data_dir = str(tmp_path)
    monkeypatch.setattr("services.application.get_settings", lambda: settings)
    uri = service.add("cover-letters/draft", letter.model_dump())

    result = CliRunner().invoke(main, ["export-markdown", "cover-letters"])

    assert result.exit_code == 0, result.output
    assert "Re-exported 1 markdown file(s)" in result.stdout
    assert b"I build reliable tools." in service.get_document(f"{uri}/cover-letter.md")


@pytest.mark.parametrize(
    "uri,filename",
    [
        ("cvs/base", "base.tex"),
        ("job-postings/acme/cvs/tailored", "acme-tailored.tex"),
        ("cover-letters/letter", "letter.tex"),
    ],
)
def test_stored_rendering_preserves_default_filenames(
    service, letter, tmp_path, monkeypatch, uri, filename
):
    if uri.startswith("cover-letters/"):
        content = letter.model_dump()
    else:
        content = {
            "name": "Jane Doe",
            "profession": "Engineer",
            "contact": letter.contact.model_dump(),
            "core_expertise": [],
            "qualifications": [],
            "education": [],
            "experience": [],
            "additional_experience": [],
            "areas_of_expertise": [],
            "languages": [],
        }
    if uri.startswith("job-postings/"):
        service.add(
            "job-postings/acme",
            {
                "company": "Acme",
                "title": "Engineer",
                "experience_level": "Senior",
                "industry": "Software",
                "description": "Build tools",
            },
        )
    service.add(uri, content)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(main, ["render", uri, "-f", "tex"], obj=service)

    assert result.exit_code == 0, result.output
    assert "Jane Doe" in (tmp_path / filename).read_text()
