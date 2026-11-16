"""Optimization producer and loading through public application and CLI boundaries."""

import json

import pytest
from click.testing import CliRunner
from pydantic import BaseModel

from models import Contact, CurriculumVitae
from repositories import FileSystemRepository
from services import ApplicationService
from services.analyzers.cv_optimizer import CvOptimizer
from services.analyzers.models import OptimizerOutput
from ui.cli import main

POSTING = {
    "company": "Acme",
    "title": "Engineer",
    "experience_level": "Senior",
    "industry": "Software",
    "description": "Build tools",
}


class SkillsGap(BaseModel):
    missing: list[str]


def build_cv(profession):
    return CurriculumVitae(
        name="Jane Doe",
        profession=profession,
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


class FakeCvOptimization:
    """Stands in for the LLM crew: tailors the profession and keeps what it got."""

    def __init__(self):
        self.received = None

    def optimize(self, cv, job_posting):
        self.received = (cv, job_posting)
        return OptimizerOutput(
            cv=build_cv(f"{job_posting.title} at {job_posting.company}"),
            artifacts={"skills-gap.json": SkillsGap(missing=["Go"])},
        )


@pytest.fixture
def optimization():
    return FakeCvOptimization()


@pytest.fixture
def service(tmp_path, optimization):
    service = ApplicationService(
        repository=FileSystemRepository(str(tmp_path)),
        cv_optimizer=CvOptimizer(optimization),
    )
    service.add("cvs/backend", build_cv("Engineer").model_dump())
    service.add("job-postings/acme", POSTING)
    return service


def test_optimize_produces_named_outputs_without_saving(service, optimization):
    outputs = service.optimize("cvs/backend", "job-postings/acme")

    assert outputs == {
        "base_cv_uri": "cvs/backend",
        "curriculum-vitae.json": build_cv("Engineer at Acme").model_dump(mode="json"),
        "skills-gap.json": {"missing": ["Go"]},
    }
    cv, posting = optimization.received
    assert cv == build_cv("Engineer")
    assert (posting.company, posting.title) == ("Acme", "Engineer")
    assert service.list("job-postings/acme/cvs") == []


def test_loading_an_optimization_creates_that_optimized_cv(service):
    outputs = service.optimize("cvs/backend", "job-postings/acme")

    uri = service.load("job-postings/acme/cvs/tailored", outputs)

    assert uri == "job-postings/acme/cvs/tailored"
    assert service.get(uri) == build_cv("Engineer at Acme")
    [record] = service.get("job-postings/acme/cvs")
    assert record.identifier == "tailored"
    assert record.job_posting_identifier == "acme"
    assert record.base_cv_identifier == "backend"
    assert (record.job_title, record.company) == ("Engineer", "Acme")
    assert json.loads(service.get_document(f"{uri}/skills-gap.json")) == {
        "missing": ["Go"]
    }
    assert service.list(uri) == [
        f"{uri}/curriculum-vitae.json",
        f"{uri}/skills-gap.json",
    ]


@pytest.mark.parametrize("provenance", [{}, {"base_cv_uri": None}])
def test_loading_without_a_base_cv_leaves_provenance_null(service, provenance):
    outputs = {"curriculum-vitae.json": build_cv("Engineer").model_dump(), **provenance}

    uri = service.load("job-postings/acme/cvs/tailored", outputs)

    [record] = service.get("job-postings/acme/cvs")
    assert record.base_cv_identifier is None
    assert service.list(uri) == [f"{uri}/curriculum-vitae.json"]


@pytest.mark.parametrize(
    "base_cv_uri", ["cvs/missing", "job-postings/acme", "cvs/backend/notes.md", 42]
)
def test_loading_with_a_base_cv_uri_that_names_no_base_cv_writes_nothing(
    service, base_cv_uri
):
    outputs = {
        "base_cv_uri": base_cv_uri,
        "curriculum-vitae.json": build_cv("Engineer").model_dump(),
    }

    with pytest.raises(ValueError, match="base_cv_uri"):
        service.load("job-postings/acme/cvs/tailored", outputs)

    assert service.list("job-postings/acme/cvs") == []


@pytest.mark.parametrize(
    "destination, message",
    [
        ("job-postings/acme/cvs", "Cannot load into job-postings/acme/cvs"),
        ("job-postings/acme/cvs/", "Cannot load into job-postings/acme/cvs/"),
        ("optimized-cvs/tailored", "Cannot load into optimized-cvs/tailored"),
        ("job-postings/missing/cvs/tailored", "Not found: job-postings/missing"),
        ("job-postings/acme/cvs/tai lored", "identifier"),
    ],
)
def test_loading_an_optimization_elsewhere_writes_nothing(
    service, destination, message
):
    outputs = service.optimize("cvs/backend", "job-postings/acme")

    with pytest.raises(ValueError, match=message):
        service.load(destination, outputs)

    assert service.list("optimized-cvs", recursive=True) == []


def test_loading_an_optimization_under_a_taken_identifier_keeps_the_existing_one(
    service,
):
    uri = "job-postings/acme/cvs/tailored"
    service.add(uri, build_cv("Engineer").model_dump())
    outputs = service.optimize("cvs/backend", "job-postings/acme")

    with pytest.raises(ValueError, match=f"Already exists: {uri}"):
        service.load(uri, outputs)

    assert service.get(uri) == build_cv("Engineer")
    assert service.list(uri) == [f"{uri}/curriculum-vitae.json"]


def test_cli_optimize_output_loads_into_the_posting(service):
    optimized = CliRunner(mix_stderr=False).invoke(
        main, ["optimize", "cvs/backend", "job-postings/acme"], obj=service
    )
    assert optimized.exit_code == 0, optimized.stderr
    assert json.loads(optimized.stdout) == service.optimize(
        "cvs/backend", "job-postings/acme"
    )
    assert service.list("job-postings/acme/cvs") == []

    loaded = CliRunner(mix_stderr=False).invoke(
        main,
        ["load", "job-postings/acme/cvs/tailored"],
        input=optimized.stdout,
        obj=service,
    )

    assert loaded.exit_code == 0, loaded.stderr
    assert loaded.stdout == "job-postings/acme/cvs/tailored\n"
    [record] = service.get("job-postings/acme/cvs")
    assert record.base_cv_identifier == "backend"


WRONG_INPUTS = [
    (["cvs/missing", "job-postings/acme"], "cvs/missing"),
    (["cvs/backend", "job-postings/missing"], "job-postings/missing"),
    (["job-postings/acme", "job-postings/acme"], "job-postings/acme"),
    (["job-postings/acme/cvs/tailored", "job-postings/acme"], "cvs/tailored"),
    (["cvs/backend", "cvs/backend"], "cvs/backend"),
    (["cvs/backend/notes.md", "job-postings/acme"], "cvs/backend/notes.md"),
]


@pytest.fixture
def tailored(service):
    service.add("job-postings/acme/cvs/tailored", build_cv("Engineer").model_dump())


@pytest.mark.parametrize("arguments, culprit", WRONG_INPUTS)
def test_optimize_rejects_inputs_other_than_a_base_cv_and_a_posting(
    service, optimization, tailored, arguments, culprit
):
    with pytest.raises(ValueError, match=culprit):
        service.optimize(*arguments)

    assert optimization.received is None


@pytest.mark.parametrize("arguments, culprit", WRONG_INPUTS)
def test_cli_optimize_reports_wrong_inputs_as_usage_errors(
    service, optimization, tailored, arguments, culprit
):
    result = CliRunner(mix_stderr=False).invoke(
        main, ["optimize", *arguments], obj=service
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    assert culprit in result.stderr
    assert optimization.received is None


def test_cli_optimize_does_not_catch_optimizer_failures(service, optimization):
    def fail(cv, job_posting):
        raise ValueError("Crew did not produce a cv.json output")

    optimization.optimize = fail

    result = CliRunner(mix_stderr=False).invoke(
        main, ["optimize", "cvs/backend", "job-postings/acme"], obj=service
    )

    assert isinstance(result.exception, ValueError)
    assert "Error:" not in result.stderr


PLAN = {"job_title": "Engineer", "company": "Acme", "missing_skills": ["Go"]}


def load_optimization_with_plan(service, plan):
    """Load an optimized CV supported by plan, then archive its posting."""
    service.load(
        "job-postings/acme/cvs/tailored",
        {
            "curriculum-vitae.json": build_cv("Engineer").model_dump(),
            "cv-transformation-plan.json": plan,
        },
    )
    service.archive_job_posting("acme")


def test_reading_an_optimization_finds_its_plan_by_filename(service):
    load_optimization_with_plan(service, PLAN)

    plan, cv = service.get_cv_optimization("acme", "tailored")

    assert plan["missing_skills"] == ["Go"]
    assert cv == build_cv("Engineer").model_dump()


def test_reading_an_optimization_skips_a_plan_that_does_not_parse(service, caplog):
    load_optimization_with_plan(service, {"job_title": "Engineer"})

    plan, cv = service.get_cv_optimization("acme", "tailored")

    assert plan == {}
    assert cv == build_cv("Engineer").model_dump()
    assert "cv-transformation-plan.json" in caplog.text


def test_exporting_optimizations_converts_a_plan_found_by_filename(service, tmp_path):
    load_optimization_with_plan(service, PLAN)

    count = service.export_markdown(collection_name="optimizations")

    directory = tmp_path / "job-postings/archived/acme/cvs/tailored"
    assert count == 2
    assert "Go" in (directory / "cv-transformation-plan.md").read_text()
    assert (directory / "curriculum-vitae.md").exists()


def test_exporting_optimizations_skips_a_plan_that_does_not_parse(
    service, tmp_path, caplog
):
    load_optimization_with_plan(service, "not a plan")

    count = service.export_markdown(collection_name="optimizations")

    directory = tmp_path / "job-postings/archived/acme/cvs/tailored"
    assert count == 1
    assert not (directory / "cv-transformation-plan.md").exists()
    assert "cv-transformation-plan.json" in caplog.text
