"""Producing and loading contracts through the application and a real repository."""

import json
from pathlib import Path

import pytest

from models import Contact, CurriculumVitae
from repositories import FileSystemRepository
from services import ApplicationService
from services.analyzers.cv_analyzer import CvAnalyzer


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
