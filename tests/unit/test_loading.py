"""Producing and loading contracts through the application and a real repository."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from models import Contact, CurriculumVitae
from repositories import FileSystemRepository
from services import ApplicationService
from services.analyzers.cv_analyzer import CvAnalyzer
from ui.cli import main


ACME_POSTING = {
    "company": "Acme",
    "title": "Engineer",
    "experience_level": "Senior",
    "industry": "Software",
    "description": "Build tools",
}


class FakeCvAnalysis:
    """Stands in for the LLM crew: returns a fixed CV and keeps what it read."""

    def __init__(self, cv: CurriculumVitae):
        self.cv = cv
        self.read = None

    def analyze(self, file_path: str) -> CurriculumVitae:
        self.read = Path(file_path).read_text()
        return self.cv


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
def analysis(cv):
    return FakeCvAnalysis(cv)


@pytest.fixture
def service(tmp_path, analysis):
    return ApplicationService(
        repository=FileSystemRepository(str(tmp_path)),
        cv_analyzer=CvAnalyzer(analysis),
    )


def test_analyzing_a_cv_names_its_content_as_curriculum_vitae_json(
    service, analysis, cv
):
    outputs = service.analyze_cv("Jane Doe, Engineer")

    assert outputs == {"curriculum-vitae.json": cv.model_dump(mode="json")}
    assert analysis.read == "Jane Doe, Engineer"


@pytest.mark.parametrize("from_stdin", [False, True])
def test_cli_analyze_cv_prints_named_outputs(
    service, analysis, cv, tmp_path, from_stdin
):
    source = tmp_path / "resume.md"
    source.write_text("Jane Doe, Engineer")
    args, stdin = (["-"], source.read_text()) if from_stdin else ([str(source)], None)

    result = CliRunner(mix_stderr=False).invoke(
        main, ["analyze", "cv", *args], input=stdin, obj=service
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == {
        "curriculum-vitae.json": cv.model_dump(mode="json")
    }
    assert analysis.read == "Jane Doe, Engineer"
    assert service.list("cvs") == []


def test_cli_load_reads_named_outputs_from_stdin_and_prints_the_uri(service, cv):
    outputs = {"curriculum-vitae.json": cv.model_dump(mode="json"), "notes.md": "x"}

    result = CliRunner(mix_stderr=False).invoke(
        main,
        ["load", "cvs", "-i", "backend"],
        input=json.dumps(outputs),
        obj=service,
    )

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "cvs/backend\n"
    assert service.get("cvs/backend") == cv
    assert service.get_document("cvs/backend/notes.md") == b"x"


@pytest.mark.parametrize(
    "arguments, stdin, message",
    [
        (["cvs"], "{}", "Missing option '-i'"),
        (["cvs", "-i", "backend"], '{"notes.md": ""}', "Missing curriculum-vitae.json"),
        (
            ["cvs", "-i", "backend"],
            '{"curriculum-vitae.json": {"name": "Jane"}}',
            "Invalid entity content: contact: Field required (and 8 more)",
        ),
        (["cvs", "-i", "backend"], "not json", "Invalid named outputs"),
    ],
)
def test_cli_load_reports_errors_on_stderr(service, arguments, stdin, message):
    result = CliRunner(mix_stderr=False).invoke(
        main, ["load", *arguments], input=stdin, obj=service
    )

    assert result.exit_code != 0
    assert result.stdout_bytes == b""
    assert message in result.stderr
    assert service.list("cvs") == []


def test_cli_ingest_cv_analyzes_and_loads_under_the_given_identifier(
    service, analysis, cv, tmp_path
):
    source = tmp_path / "resume.md"
    source.write_text("Jane Doe, Engineer")

    result = CliRunner(mix_stderr=False).invoke(
        main, ["ingest", "cv", str(source), "-i", "backend"], obj=service
    )

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "cvs/backend\n"
    assert service.get("cvs/backend") == cv
    assert analysis.read == "Jane Doe, Engineer"


def test_cli_ingest_cv_without_identifier_generates_one_from_the_profession(service):
    def ingest():
        return CliRunner(mix_stderr=False).invoke(
            main, ["ingest", "cv"], input="Jane Doe, Engineer", obj=service
        )

    first, second = ingest(), ingest()

    assert first.exit_code == 0, first.stderr
    assert first.stdout == "cvs/engineer\n"
    assert second.stdout == "cvs/engineer-2\n"


def test_loading_into_cvs_creates_a_base_cv_from_its_primary_file(service, cv):
    outputs = {"curriculum-vitae.json": cv.model_dump(mode="json")}

    uri = service.load("cvs", outputs, identifier="backend")

    assert uri == "cvs/backend"
    assert service.get(uri) == cv


def test_loading_keeps_other_outputs_as_documents_of_the_entity(service, cv):
    outputs = {
        "curriculum-vitae.json": cv.model_dump(mode="json"),
        "notes.md": "# Notes\n",
        "skills.json": {"languages": ["Python", "Go"]},
    }

    service.load("cvs", outputs, identifier="backend")

    assert service.get_document("cvs/backend/notes.md") == b"# Notes\n"
    assert json.loads(service.get_document("cvs/backend/skills.json")) == {
        "languages": ["Python", "Go"]
    }


def test_loading_accepts_named_outputs_as_json_text(service, cv):
    outputs = json.dumps({"curriculum-vitae.json": cv.model_dump(mode="json")})

    uri = service.load("cvs", outputs, identifier="backend")

    assert service.get(uri) == cv


@pytest.mark.parametrize(
    "build_outputs, error",
    [
        (lambda cv: {"notes.md": "# Notes\n"}, "Missing curriculum-vitae.json"),
        (
            lambda cv: {"curriculum-vitae.json": cv, "../escape.md": "x"},
            "filename",
        ),
        (
            lambda cv: {"curriculum-vitae.json": cv, "base_uri": "cvs/other"},
            "base_uri",
        ),
        (
            lambda cv: {"curriculum-vitae.json": {"name": "Jane Doe"}, "notes.md": ""},
            "CurriculumVitae",
        ),
    ],
)
def test_loading_invalid_outputs_writes_nothing(service, cv, build_outputs, error):
    outputs = build_outputs(cv.model_dump(mode="json"))

    with pytest.raises(ValueError, match=error):
        service.load("cvs", outputs, identifier="backend")

    assert service.list("cvs") == []


def test_loading_with_an_invalid_identifier_writes_nothing(service, cv):
    outputs = {"curriculum-vitae.json": cv.model_dump(mode="json")}

    with pytest.raises(ValueError, match="identifier"):
        service.load("cvs", outputs, identifier="back end")

    assert service.list("cvs") == []


def test_loading_under_a_taken_identifier_leaves_the_existing_entity_alone(service, cv):
    service.add("cvs", cv.model_dump(), identifier="backend")
    outputs = {"curriculum-vitae.json": cv.model_dump(mode="json"), "notes.md": "x"}

    with pytest.raises(ValueError, match="Already exists: cvs/backend"):
        service.load("cvs", outputs, identifier="backend")

    assert "cvs/backend/notes.md" not in service.list("cvs/backend")


@pytest.mark.parametrize(
    "destination", ["job-postings", "job-postings/acme/cvs", "optimized-cvs"]
)
def test_loading_outside_cvs_is_not_supported_yet(service, cv, destination):
    service.add("job-postings", ACME_POSTING, identifier="acme")
    outputs = {"curriculum-vitae.json": cv.model_dump(mode="json")}

    with pytest.raises(ValueError, match=f"Cannot load into {destination}"):
        service.load(destination, outputs, identifier="backend")

    assert service.list("job-postings/acme/cvs") == []
