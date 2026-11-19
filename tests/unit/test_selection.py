"""Reading contracts through the application and a real repository."""

import json

import pytest
import click
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


@pytest.fixture
def complete(service):
    """Complete a command line through Click with the real application."""
    shell = ShellComplete(main, {"obj": service}, "cv-joint", "_CV_JOINT_COMPLETE")

    def values(args, incomplete):
        return [item.value for item in shell.get_completions(args, incomplete)]

    return values


@pytest.fixture
def two_postings(service, posting, cv):
    """A base CV and two postings, each with an optimized CV named backend."""
    service.add("cvs/backend", cv.model_dump())
    for identifier in ("acme", "other"):
        service.add(f"job-postings/{identifier}", posting.model_dump())
        service.add(f"job-postings/{identifier}/cvs/backend", cv.model_dump())


def test_job_posting_completion_offers_canonical_uris_in_every_location(
    service, posting
):
    for identifier in ("acme", "beta", "other"):
        service.add(f"job-postings/{identifier}", posting.model_dump())
    service.transition_job_posting("acme", "applied")
    service.archive_job_posting("beta")

    assert service.complete_job_posting_uris("") == [
        "job-postings/acme",
        "job-postings/beta",
        "job-postings/other",
    ]
    assert service.complete_job_posting_uris("job-postings/b") == ["job-postings/beta"]
    assert service.complete_job_posting_uris("cvs/") == []


@pytest.mark.parametrize(
    "args",
    [
        ["transition"],
        ["archive"],
        ["unarchive"],
        ["apply"],
        ["optimize", "cvs/backend"],
    ],
)
def test_cli_job_posting_completion_uses_canonical_uris(
    service, posting, cv, complete, args
):
    service.add("cvs/backend", cv.model_dump())
    service.add("job-postings/acme", posting.model_dump())
    service.transition_job_posting("acme", "applied")

    assert complete(args, "job") == ["job-postings/acme"]


@pytest.mark.usefixtures("two_postings")
@pytest.mark.parametrize("job_posting_uri", ["job-postings/acme", "job-postings/acme/"])
def test_cv_completion_uses_canonical_uris_for_selected_posting(
    service, job_posting_uri
):
    service.transition_job_posting("acme", "archived")

    assert service.complete_cv_identifiers("", job_posting_uri=job_posting_uri) == [
        "cvs/backend",
        "job-postings/acme/cvs/backend",
    ]
    assert service.complete_cv_identifiers("job", job_posting_uri=job_posting_uri) == [
        "job-postings/acme/cvs/backend",
    ]


@pytest.mark.usefixtures("two_postings")
@pytest.mark.parametrize("job_posting_uri", [None, "", "cvs/backend", "nonsense"])
def test_cv_completion_offers_only_base_cvs_without_a_posting(service, job_posting_uri):
    assert service.complete_cv_identifiers("", job_posting_uri=job_posting_uri) == [
        "cvs/backend"
    ]


@pytest.mark.usefixtures("two_postings")
@pytest.mark.parametrize("job_posting_uri", ["job-postings/acme", "job-postings/acme/"])
def test_apply_completion_offers_selected_postings_optimized_cv(
    complete, job_posting_uri
):
    assert complete(["apply", job_posting_uri], "") == [
        "cvs/backend",
        "job-postings/acme/cvs/backend",
    ]


@pytest.mark.usefixtures("two_postings")
def test_optimize_completion_offers_only_base_cvs(complete):
    assert complete(["optimize"], "") == ["cvs/backend"]


def test_get_and_list_select_unfiled_postings(service, posting):
    service.add("job-postings/active", posting.model_dump())
    service.add("job-postings/filed", posting.model_dump())
    service.transition_job_posting("filed", "applied")

    assert [record.identifier for record in service.get("job-postings")] == ["active"]
    assert service.list("job-postings") == ["job-postings/active"]


def test_location_selection_and_recursive_scope(service, posting):
    for identifier in ("active", "filed", "old"):
        service.add(f"job-postings/{identifier}", posting.model_dump())
    service.transition_job_posting("filed", "applied")
    service.transition_job_posting("old", "archived")

    assert service.list("job-postings/applied") == ["job-postings/filed"]
    for target in ("job-postings", "job-postings/applied"):
        assert [
            record.identifier for record in service.get(target, recursive=True)
        ] == ["active", "filed", "old"]
        assert service.list(target, recursive=True) == [
            "job-postings/active",
            "job-postings/filed",
            "job-postings/old",
        ]


@pytest.mark.parametrize("query", ["REFERRAL", '"channel":"referral"', "transitions"])
def test_query_matches_the_whole_serialized_record(service, posting, query):
    service.add("job-postings/filed", posting.model_dump())
    service.transition_job_posting("filed", "applied", fields={"channel": "Referral"})

    assert [
        record.identifier
        for record in service.get("job-postings", recursive=True, query=query)
    ] == ["filed"]
    assert service.list("job-postings", recursive=True, query=query) == [
        "job-postings/filed"
    ]
    assert service.list("job-postings", recursive=True, query="no match") == []


def test_base_cv_collection_selects_records_and_canonical_uris(service, cv):
    service.add("cvs/backend", cv.model_dump())

    assert [record.identifier for record in service.get("cvs", query="JANE")] == [
        "backend"
    ]
    assert service.list("cvs", recursive=True, query="JANE") == ["cvs/backend"]
    assert service.get("cvs", query="missing") == []


@pytest.mark.parametrize(
    ("target", "recursive", "parents"),
    [
        ("optimized-cvs", False, ["active"]),
        ("optimized-cvs/applied", False, ["filed"]),
        ("optimized-cvs", True, ["active", "filed"]),
        ("optimized-cvs/applied", True, ["active", "filed"]),
        ("job-postings/filed/cvs", False, ["filed"]),
        ("job-postings/filed/cvs", True, ["filed"]),
    ],
)
def test_optimized_cv_selection_follows_parent_scope(
    service, posting, cv, target, recursive, parents
):
    for identifier in ("active", "filed"):
        service.add(f"job-postings/{identifier}", posting.model_dump())
        service.add(f"job-postings/{identifier}/cvs/backend", cv.model_dump())
    service.transition_job_posting("filed", "applied")

    assert [
        record.job_posting_identifier
        for record in service.get(target, recursive=recursive, query="JANE")
    ] == parents
    assert service.list(target, recursive=recursive, query="JANE") == [
        f"job-postings/{parent}/cvs/backend" for parent in parents
    ]
    assert service.list(target, recursive=recursive, query="absent") == []


def test_exact_entity_reads_content_regardless_of_location_or_flags(
    service, posting, cv
):
    service.add("job-postings/acme", posting.model_dump())
    service.add("cvs/base", cv.model_dump())
    service.add("job-postings/acme/cvs/backend", cv.model_dump())
    service.transition_job_posting("acme", "applied")

    for target, content in [
        ("job-postings/acme", posting),
        ("cvs/base", cv),
        ("job-postings/acme/cvs/backend", cv),
    ]:
        assert service.get(target, recursive=True, query="does not match") == content


def test_location_wins_over_posting_with_same_identifier(service, posting):
    for identifier in ("applied", "acme"):
        service.add(f"job-postings/{identifier}", posting.model_dump())
    service.transition_job_posting("acme", "applied")
    assert [record.identifier for record in service.get("job-postings/applied")] == [
        "acme"
    ]
    assert service.list("job-postings/applied") == ["job-postings/acme"]


@pytest.mark.parametrize("target", ["job-postings", "cvs", "optimized-cvs"])
def test_empty_collection_has_no_records_or_uris(service, target):
    assert service.get(target) == []
    assert service.list(target) == []


@pytest.mark.parametrize(
    "target",
    [
        "job-postings/ac",
        "cvs/missing",
        "job-postings/missing/cvs",
        "job-postings/applied/acme",
        "optimized-cvs/missing",
    ],
)
def test_missing_and_legacy_targets_fail_instead_of_prefix_matching(
    service, posting, target
):
    service.add("job-postings/acme", posting.model_dump())
    service.transition_job_posting("acme", "applied")
    with pytest.raises(ValueError):
        service.get(target)
    with pytest.raises(ValueError):
        service.list(target)


def test_list_entity_names_documents_and_child_collections(service, posting, cv):
    service.add("job-postings/acme", posting.model_dump())
    service.add("cvs/base", cv.model_dump())
    service.add("job-postings/acme/cvs/backend", cv.model_dump())
    service.add_document("job-postings/acme/job-posting.md", b"# Posting")
    service.add_document("cvs/base/curriculum-vitae.md", b"# Base CV")
    service.add_document("job-postings/acme/cvs/backend/curriculum-vitae.md", b"# CV")
    service.transition_job_posting("acme", "applied")

    assert service.list("job-postings/acme", recursive=True, query="ignored") == [
        "job-postings/acme/job-posting.json",
        "job-postings/acme/job-posting.md",
        "job-postings/acme/cvs",
    ]
    assert service.list("cvs/base") == [
        "cvs/base/curriculum-vitae.json",
        "cvs/base/curriculum-vitae.md",
    ]
    assert service.list("job-postings/acme/cvs/backend") == [
        "job-postings/acme/cvs/backend/curriculum-vitae.json",
        "job-postings/acme/cvs/backend/curriculum-vitae.md",
    ]


def test_document_read_preserves_binary_bytes_after_parent_moves(service, posting, cv):
    service.add("job-postings/acme", posting.model_dump())
    service.add("job-postings/acme/cvs/backend", cv.model_dump())
    content = b"%PDF-1.7\r\n\x00\xff\xfe\n"
    service.add_document("job-postings/acme/cvs/backend/application.pdf", content)
    service.transition_job_posting("acme", "applied")

    assert (
        service.get_document("job-postings/acme/cvs/backend/application.pdf") == content
    )
    with pytest.raises(FileNotFoundError):
        service.get_document("job-postings/acme/cvs/backend/missing.pdf")


def test_cli_get_and_list_render_the_same_selection(service, posting):
    service.add("job-postings/acme", posting.model_dump())
    service.transition_job_posting("acme", "applied", fields={"channel": "Referral"})
    runner = CliRunner()

    records = runner.invoke(
        main, ["get", "job-postings", "-r", "-q", "REFERRAL"], obj=service
    )
    uris = runner.invoke(
        main, ["list", "job-postings", "-r", "-q", "REFERRAL"], obj=service
    )
    assert records.exit_code == uris.exit_code == 0
    lines = records.stdout.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["identifier"] == "acme"
    assert '"channel":"Referral"' in lines[0]
    assert uris.stdout == "job-postings/acme\n"


@pytest.mark.parametrize(
    "content",
    [
        b"%PDF-1.7\r\n\x00\xff\xfe",
        b'{"untouched": true}\r\n',
        b"plain text without newline",
    ],
)
def test_cli_document_output_is_always_raw_bytes(service, cv, content):
    service.add("cvs/base", cv.model_dump())
    service.add_document("cvs/base/attachment", content)

    result = CliRunner().invoke(
        main, ["get", "cvs/base/attachment", "-r", "-q", "ignored"], obj=service
    )
    assert result.exit_code == 0, result.output
    assert result.stdout_bytes == content


def test_completion_offers_logical_targets_in_every_location(service, posting, cv):
    service.add("job-postings/acme", posting.model_dump())
    service.add("job-postings/acme/cvs/backend", cv.model_dump())
    service.add("cvs/base", cv.model_dump())
    service.add_document("job-postings/acme/job-posting.md", b"# Posting")
    service.add_document("cvs/base/curriculum-vitae.md", b"# Base CV")
    service.add_document("job-postings/acme/cvs/backend/curriculum-vitae.md", b"# CV")
    service.transition_job_posting("acme", "applied")

    assert service.complete_targets("job-postings/") == [
        "job-postings/acme",
        "job-postings/acme/cvs",
        "job-postings/acme/cvs/backend",
        "job-postings/acme/cvs/backend/curriculum-vitae.json",
        "job-postings/acme/cvs/backend/curriculum-vitae.md",
        "job-postings/acme/job-posting.json",
        "job-postings/acme/job-posting.md",
        "job-postings/applied",
    ]
    assert service.complete_targets("optimized-cvs") == [
        "optimized-cvs",
        "optimized-cvs/applied",
    ]
    assert service.complete_targets("cvs/ba") == [
        "cvs/base",
        "cvs/base/curriculum-vitae.json",
        "cvs/base/curriculum-vitae.md",
    ]


@pytest.mark.parametrize("command", ["get", "list", "ls"])
def test_cli_completion_uses_canonical_targets(service, posting, command):
    service.add("job-postings/acme", posting.model_dump())
    service.add_document("job-postings/acme/job-posting.md", b"# Posting")
    service.transition_job_posting("acme", "applied")
    cli_command = main.commands[command]
    context = click.Context(cli_command, obj=service)

    candidates = cli_command.params[0].shell_complete(context, "job-postings/")
    assert [candidate.value for candidate in candidates] == [
        "job-postings/acme",
        "job-postings/acme/cvs",
        "job-postings/acme/job-posting.json",
        "job-postings/acme/job-posting.md",
        "job-postings/applied",
    ]


def test_add_completion_offers_destination_prefixes_ending_in_a_slash(
    service, posting, cv
):
    service.add("job-postings/acme", posting.model_dump())
    service.add("job-postings/acme/cvs/backend", cv.model_dump())
    service.add("cvs/base", cv.model_dump())
    service.transition_job_posting("acme", "applied")

    assert service.complete_add_destinations("") == [
        "cover-letters/",
        "cvs/",
        "cvs/base/",
        "job-postings/",
        "job-postings/acme/",
        "job-postings/acme/cvs/",
        "job-postings/acme/cvs/backend/",
    ]
    assert service.complete_add_destinations("job-postings/acme/c") == [
        "job-postings/acme/cvs/",
        "job-postings/acme/cvs/backend/",
    ]


def test_load_completion_offers_collection_prefixes_ending_in_a_slash(
    service, posting, cv
):
    service.add("job-postings/acme", posting.model_dump())
    service.add("cvs/base", cv.model_dump())
    service.transition_job_posting("acme", "applied")

    assert service.complete_load_destinations("") == [
        "cvs/",
        "job-postings/",
        "job-postings/acme/cvs/",
    ]


def test_cli_load_completion_uses_collection_prefixes(service, posting):
    service.add("job-postings/acme", posting.model_dump())
    cli_command = main.commands["load"]
    context = click.Context(cli_command, obj=service)

    candidates = cli_command.params[0].shell_complete(context, "job-postings/")
    assert [candidate.value for candidate in candidates] == [
        "job-postings/",
        "job-postings/acme/cvs/",
    ]


def test_cli_add_completion_uses_destination_prefixes(service, posting):
    service.add("job-postings/acme", posting.model_dump())
    cli_command = main.commands["add"]
    context = click.Context(cli_command, obj=service)

    candidates = cli_command.params[0].shell_complete(context, "job-postings/")
    assert [candidate.value for candidate in candidates] == [
        "job-postings/",
        "job-postings/acme/",
        "job-postings/acme/cvs/",
    ]


@pytest.mark.parametrize("command", ["get", "list", "ls"])
@pytest.mark.parametrize("target", ["job-postings", "cvs", "optimized-cvs"])
def test_cli_empty_selection_prints_nothing(service, command, target):
    result = CliRunner().invoke(main, [command, target], obj=service)
    assert result.exit_code == 0
    assert result.stdout_bytes == b""


@pytest.mark.parametrize("command", ["get", "list"])
@pytest.mark.parametrize(
    "target",
    [
        "dogs",
        "job-postings/ac",
        "job-postings/applied/acme",
        "cvs/missing",
        "job-postings/acme/missing.pdf",
    ],
)
def test_cli_missing_or_invalid_target_reports_error_on_stderr(
    service, posting, command, target
):
    service.add("job-postings/acme", posting.model_dump())
    service.transition_job_posting("acme", "applied")
    result = CliRunner(mix_stderr=False).invoke(main, [command, target], obj=service)
    assert result.exit_code != 0
    assert result.stdout_bytes == b""
    assert "Error:" in result.stderr


def test_cli_exact_entity_prints_content_and_ignores_selection_flags(service, cv):
    service.add("cvs/base", cv.model_dump())
    result = CliRunner().invoke(
        main, ["get", "cvs/base", "-r", "-q", "ignored"], obj=service
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout) == cv.model_dump(mode="json")


def test_completion_offers_collections_without_any_records(service):
    assert service.complete_targets("") == [
        "cover-letters",
        "cvs",
        "job-postings",
        "optimized-cvs",
    ]
