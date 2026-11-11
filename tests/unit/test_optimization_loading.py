"""Optimization through public application and CLI boundaries."""

import json

import pytest
from click.testing import CliRunner

from models import Contact, CurriculumVitae, CvTransformationPlan
from repositories import FileSystemRepository
from services import ApplicationService
from services.analyzers import CvOptimizer
from services.analyzers.models import OptimizerOutput
from ui.cli import main


POSTING = {
    "company": "Acme",
    "title": "Engineer",
    "experience_level": "Senior",
    "industry": "Software",
    "description": "Build tools",
}
DESTINATION = "job-postings/acme/cvs/backend"


class FakeOptimization:
    def __init__(self, with_plan=True):
        self.with_plan = with_plan

    def optimize(self, cv, job_posting):
        return OptimizerOutput(
            cv=cv.model_copy(update={"profession": job_posting.title}),
            artifacts={
                "transformation-plan": CvTransformationPlan(
                    job_title=job_posting.title, company=job_posting.company
                )
            }
            if self.with_plan
            else {},
        )


@pytest.fixture
def cv():
    return CurriculumVitae(
        name="Jane Doe",
        profession="Developer",
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
def service(tmp_path, cv, request):
    service = ApplicationService(
        repository=FileSystemRepository(str(tmp_path)),
        cv_optimizer=CvOptimizer(FakeOptimization(getattr(request, "param", True))),
    )
    service.add("cvs/base", cv.model_dump(mode="json"))
    service.add("job-postings/acme", POSTING)
    return service


def test_optimize_produces_named_outputs_without_saving(service):
    outputs = service.optimize("cvs/base", "job-postings/acme")

    assert outputs["base_uri"] == "cvs/base"
    assert outputs["curriculum-vitae.json"]["profession"] == "Engineer"
    assert outputs["cv-transformation-plan.json"]["company"] == "Acme"
    json.dumps(outputs)
    assert service.list("job-postings/acme/cvs") == []
    assert service.get("cvs/base").profession == "Developer"


def test_load_optimized_cv_with_only_primary_content(service, cv):
    uri = service.load(
        DESTINATION, {"curriculum-vitae.json": cv.model_dump(mode="json")}
    )

    assert uri == DESTINATION
    assert service.get(uri) == cv
    record = service.get("job-postings/acme/cvs")[0]
    assert record.base_cv_identifier is None
    assert record.company == "Acme"
    assert record.job_title == "Engineer"


@pytest.mark.parametrize("base_uri", ["cvs/base", None])
def test_load_preserves_provenance_and_ordinary_supporting_outputs(
    service, cv, base_uri
):
    service.archive_job_posting("acme")
    outputs = {
        "curriculum-vitae.json": cv.model_dump(mode="json"),
        "base_uri": base_uri,
        "cv-transformation-plan.json": {"arbitrary": "supporting content"},
        "notes.md": "# Notes\n",
    }
    uri = service.load(DESTINATION, json.dumps(outputs))

    record = service.get("job-postings/acme/cvs")[0]
    assert record.base_cv_identifier == ("base" if base_uri else None)
    assert json.loads(service.get_document(f"{uri}/cv-transformation-plan.json")) == {
        "arbitrary": "supporting content"
    }
    assert service.get_document(f"{uri}/notes.md") == b"# Notes\n"
    assert f"{uri}/base_uri" not in service.list(uri)


def test_cli_optimize_output_can_be_loaded(service):
    runner = CliRunner(mix_stderr=False)
    produced = runner.invoke(
        main, ["optimize", "cvs/base", "job-postings/acme"], obj=service
    )
    assert produced.exit_code == 0, produced.stderr
    assert service.list("job-postings/acme/cvs") == []
    loaded = runner.invoke(
        main, ["load", DESTINATION], input=produced.stdout, obj=service
    )
    assert loaded.exit_code == 0, loaded.stderr
    assert loaded.stdout == f"{DESTINATION}\n"
    assert service.get(DESTINATION).profession == "Engineer"
    assert service.get("job-postings/acme/cvs")[0].base_cv_identifier == "base"


@pytest.mark.parametrize(
    "cv_uri, posting_uri",
    [
        ("job-postings/acme", "cvs/base"),
        ("cvs", "job-postings/acme"),
        ("cvs/missing", "job-postings/acme"),
        ("cvs/base", "job-postings/missing"),
    ],
)
def test_cli_optimize_rejects_invalid_sources(service, cv_uri, posting_uri):
    result = CliRunner(mix_stderr=False).invoke(
        main, ["optimize", cv_uri, posting_uri], obj=service
    )
    assert result.exit_code != 0
    assert result.stdout == ""
    assert "Error:" in result.stderr
    assert service.list("job-postings/acme/cvs") == []


@pytest.mark.parametrize(
    "changes",
    [
        {"base_uri": "cvs/missing"},
        {"base_uri": "job-postings/acme"},
        {"base_uri": 5},
        {"base_uri": "garbage"},
        {"../escape": "bad"},
        {"notes.json": {1, 2}},
        {"curriculum-vitae.json": {}},
    ],
)
def test_invalid_load_writes_nothing(service, cv, changes):
    outputs = {"curriculum-vitae.json": cv.model_dump(mode="json"), **changes}
    with pytest.raises(ValueError):
        service.load(DESTINATION, outputs)
    assert service.list("job-postings/acme/cvs") == []


def test_loading_at_existing_destination_preserves_content(service, cv):
    service.load(DESTINATION, {"curriculum-vitae.json": cv.model_dump(mode="json")})
    with pytest.raises(ValueError, match="Already exists"):
        service.load(DESTINATION, service.optimize("cvs/base", "job-postings/acme"))
    assert service.get(DESTINATION).profession == "Developer"
    assert service.get("job-postings/acme/cvs")[0].base_cv_identifier is None


@pytest.mark.parametrize("with_plan", [False, True])
def test_loaded_optimization_can_be_previewed_and_exported(service, with_plan):
    outputs = service.optimize("cvs/base", "job-postings/acme")
    outputs["notes.json"] = ["ordinary", "supporting content"]
    if not with_plan:
        del outputs["cv-transformation-plan.json"]
    service.load(DESTINATION, outputs)
    service.archive_job_posting("acme")
    plan_data, cv_data = service.get_cv_optimization("acme", "backend")
    assert "Jane Doe" in service.to_markdown(CurriculumVitae(**cv_data))
    if with_plan:
        assert "Acme" in service.to_markdown(CvTransformationPlan(**plan_data))
    else:
        assert plan_data == {}
    assert service.export_markdown("optimizations") == (2 if with_plan else 1)
    assert b"Jane Doe" in service.get_document(f"{DESTINATION}/curriculum-vitae.md")
    if with_plan:
        assert b"Acme" in service.get_document(
            f"{DESTINATION}/cv-transformation-plan.md"
        )


@pytest.mark.parametrize("service", [True, False], indirect=True)
def test_gradio_optimization_preview_save_and_reopen(service, request):
    from ui.app import create_app

    app = create_app(service=service)
    callbacks = {
        function.fn.__name__: function.fn
        for function in app.fns.values()
        if function.fn
    }
    preview = callbacks["run_optimization"]("acme", "base")
    with_plan = request.node.callspec.params["service"]
    assert ("Acme" in preview[1]) if with_plan else preview[1] == ""
    assert "Jane Doe" in preview[3]
    assert service.list("job-postings/acme/cvs") == []
    identifiers = {**preview[5], "identifier": "backend"}
    saved = callbacks["save_optimization"](identifiers, False, preview[0], preview[2])
    assert saved[1] is True, saved[0]
    assert service.get(DESTINATION).profession == "Engineer"
    assert service.get("job-postings/acme/cvs")[0].base_cv_identifier == "base"
    from gradio import SelectData

    reopened = callbacks["view_saved_optimization"](
        SelectData(
            None,
            {
                "index": [0, 0],
                "value": "",
                "row_value": ["", "", "", "acme", "backend"],
            },
        )
    )
    assert ("Acme" in reopened[1]) if with_plan else reopened[1] == ""
    assert "Jane Doe" in reopened[3]
    app.close()
