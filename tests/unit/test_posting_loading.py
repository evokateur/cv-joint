"""Posting producers and loading through public application and CLI boundaries."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from models import JobPosting
from repositories import FileSystemRepository
from services import ApplicationService
from services.analyzers import JobPostingAnalyzer
from ui.cli import main

POSTING = {
    "company": "Acme",
    "title": "Engineer",
    "experience_level": "Senior",
    "industry": "Software",
    "description": "Build tools",
}
URL = "https://example.com/jobs/123"


class FakePostingAnalysis:
    def __init__(self):
        self.read = None

    def analyze(self, content_file):
        self.read = Path(content_file).read_text()
        return JobPosting(**POSTING, url="https://example.com/extracted")


@pytest.fixture
def analysis():
    return FakePostingAnalysis()


@pytest.fixture
def service(tmp_path, analysis):
    return ApplicationService(
        repository=FileSystemRepository(str(tmp_path)),
        job_posting_analyzer=JobPostingAnalyzer(analysis),
    )


def test_analyze_posting_produces_named_content_without_saving(service, analysis):
    outputs = service.analyze_job_posting("Build tools", url=URL)
    assert outputs["job-posting.json"]["url"] == URL
    assert outputs["job-posting.json"]["company"] == "Acme"
    assert analysis.read == "Build tools"
    assert service.list("job-postings") == []


@pytest.fixture
def fetched_page(monkeypatch):
    import requests

    response = requests.Response()
    response.status_code = 200
    response._content = b"<h1>Build tools</h1>"

    def fetch(url, **kwargs):
        assert url == URL
        return response

    monkeypatch.setattr(requests, "get", fetch)
    return response


def test_analyze_url_uses_fetched_page_and_sets_url(service, analysis, fetched_page):
    outputs = service.analyze_job_posting_url(URL)
    assert outputs["job-posting.json"]["url"] == URL
    assert analysis.read == "<h1>Build tools</h1>"
    assert service.list("job-postings") == []


def test_load_posting_creates_entity_and_supplied_documents(service):
    outputs = {
        "job-posting.json": POSTING,
        "job-posting.md": "# Supplied posting\n",
        "notes.json": ["call recruiter"],
    }
    uri = service.load("job-postings/acme", json.dumps(outputs))
    assert uri == "job-postings/acme"
    assert service.get(uri).company == "Acme"
    assert service.get_document(f"{uri}/job-posting.md") == b"# Supplied posting\n"
    assert json.loads(service.get_document(f"{uri}/notes.json")) == ["call recruiter"]


@pytest.mark.parametrize("arguments", [[], ["-"], ["posting.md"]])
def test_cli_analyze_posting_reads_text_and_emits_named_outputs(
    service, analysis, tmp_path, arguments
):
    source = tmp_path / "posting.md"
    source.write_text("Build tools")
    arguments = [str(source)] if arguments == ["posting.md"] else arguments
    result = CliRunner(mix_stderr=False).invoke(
        main,
        ["analyze", "job-posting", *arguments, "--url", URL],
        input="Build tools",
        obj=service,
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["job-posting.json"]["url"] == URL
    assert analysis.read == "Build tools"
    assert service.list("job-postings") == []


def test_cli_analyze_posting_url_fetches_source(service, analysis, fetched_page):
    result = CliRunner(mix_stderr=False).invoke(
        main, ["analyze", "job-posting", URL], obj=service
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["job-posting.json"]["url"] == URL
    assert analysis.read == "<h1>Build tools</h1>"


def test_cli_explicit_url_overrides_fetched_source_url(service, fetched_page):
    canonical = "https://example.com/careers/engineer"
    result = CliRunner(mix_stderr=False).invoke(
        main, ["analyze", "job-posting", URL, "--url", canonical], obj=service
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["job-posting.json"]["url"] == canonical


def test_cli_ingest_posting_loads_analyzed_text_at_explicit_uri(service, analysis):
    result = CliRunner(mix_stderr=False).invoke(
        main,
        ["ingest", "job-posting", "-", "--url", URL, "-i", "Acme"],
        input="Build tools",
        obj=service,
    )
    assert result.exit_code == 0, result.stderr
    assert result.stdout == "job-postings/Acme\n"
    assert service.get("job-postings/Acme").url == URL
    assert analysis.read == "Build tools"


def test_ingest_posting_generates_free_uri_from_content(service, fetched_page):
    runner = CliRunner(mix_stderr=False)
    first = runner.invoke(main, ["ingest", "job-posting", URL], obj=service)
    second = runner.invoke(main, ["ingest", "job-posting", URL], obj=service)
    assert first.exit_code == second.exit_code == 0
    assert first.stdout == "job-postings/acme-engineer\n"
    assert second.stdout == "job-postings/acme-engineer-2\n"
    assert service.get("job-postings/acme-engineer-2").url == URL


def test_ingest_validates_identifier_before_analysis(service, analysis):
    result = CliRunner(mix_stderr=False).invoke(
        main,
        ["ingest", "job-posting", "-i", "bad/name"],
        input="Build tools",
        obj=service,
    )
    assert result.exit_code != 0
    assert "illegal identifier" in result.stderr
    assert analysis.read is None
    assert service.list("job-postings") == []


@pytest.mark.parametrize("command", ["analyze", "ingest"])
def test_posting_analysis_failure_is_reported_on_stderr(service, analysis, command):
    def fail(content_file):
        raise ValueError("analysis failed")

    analysis.analyze = fail
    result = CliRunner(mix_stderr=False).invoke(
        main, [command, "job-posting"], input="Build tools", obj=service
    )
    assert result.exit_code != 0
    assert result.stdout == ""
    assert "Error: analysis failed" in result.stderr
    assert service.list("job-postings") == []


@pytest.mark.parametrize(
    "outputs, message",
    [
        ({"notes.md": "notes"}, "Missing job-posting.json"),
        ({"job-posting.json": {}}, "Invalid entity content"),
        ({"job-posting.json": POSTING, "../notes.md": "notes"}, "filename"),
        ({"job-posting.json": POSTING, "base_uri": "cvs/backend"}, "base_uri"),
    ],
)
def test_cli_load_invalid_posting_outputs_writes_nothing(service, outputs, message):
    result = CliRunner(mix_stderr=False).invoke(
        main, ["load", "job-postings/acme"], input=json.dumps(outputs), obj=service
    )
    assert result.exit_code != 0
    assert message in result.stderr
    assert result.stdout == ""
    assert service.list("job-postings") == []


def test_load_rejects_non_json_document_content_before_writing(service):
    with pytest.raises(ValueError, match="JSON"):
        service.load(
            "job-postings/acme", {"job-posting.json": POSTING, "raw.bin": b"binary"}
        )
    assert service.list("job-postings") == []


@pytest.mark.parametrize("outputs", ["[]", "null", '"text"', "42"])
def test_cli_load_requires_named_outputs_object(service, outputs):
    result = CliRunner(mix_stderr=False).invoke(
        main, ["load", "job-postings/acme"], input=outputs, obj=service
    )
    assert result.exit_code != 0
    assert "named outputs" in result.stderr.lower()
    assert service.list("job-postings") == []


def test_analyze_then_cli_load_creates_posting(service):
    runner = CliRunner(mix_stderr=False)
    analyzed = runner.invoke(
        main, ["analyze", "job-posting"], input="Build tools", obj=service
    )
    loaded = runner.invoke(
        main, ["load", "job-postings/acme"], input=analyzed.stdout, obj=service
    )
    assert loaded.exit_code == 0, loaded.stderr
    assert loaded.stdout == "job-postings/acme\n"
    assert service.get("job-postings/acme").url == "https://example.com/extracted"


@pytest.mark.parametrize("command", ["analyze", "ingest"])
def test_http_failure_is_reported_without_saving(service, fetched_page, command):
    fetched_page.status_code = 403
    result = CliRunner(mix_stderr=False).invoke(
        main, [command, "job-posting", URL], obj=service
    )
    assert result.exit_code != 0
    assert "403" in result.stderr
    assert result.stdout == ""
    assert service.list("job-postings") == []


def test_ingest_rejects_old_two_argument_syntax(service, analysis):
    result = CliRunner(mix_stderr=False).invoke(
        main, ["ingest", "job-posting", URL, "-"], input="Build tools", obj=service
    )
    assert result.exit_code != 0
    assert "unexpected extra argument" in result.stderr
    assert analysis.read is None


def test_load_collision_preserves_existing_posting(service):
    service.add("job-postings/acme", POSTING)
    with pytest.raises(ValueError, match="Already exists"):
        service.load(
            "job-postings/acme",
            {
                "job-posting.json": {**POSTING, "title": "Replacement"},
                "notes.md": "New",
            },
        )
    assert service.get("job-postings/acme").title == "Engineer"
    assert "job-postings/acme/notes.md" not in service.list("job-postings/acme")
