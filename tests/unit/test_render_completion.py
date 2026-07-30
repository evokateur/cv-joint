from click.shell_completion import ShellComplete

from ui import cli as cli_mod
from ui.cli import main


def _items(args, incomplete):
    sc = ShellComplete(main, {}, "cv-joint", "_CV_JOINT_COMPLETE")
    return sc.get_completions(list(args), incomplete)


def _values(args, incomplete):
    return [c.value for c in _items(args, incomplete)]


def test_position1_offers_type_literals(monkeypatch):
    monkeypatch.setattr(cli_mod, "_load_collection", lambda name: [])
    assert "cv" in _values(["render"], "cv")
    assert "cover-letter" in _values(["render"], "cover")


def test_position1_offers_renderable_cv_uris(monkeypatch):
    monkeypatch.setattr(
        cli_mod,
        "_load_collection",
        lambda name: [{"identifier": "my-cv"}] if name == "cvs" else [],
    )
    assert "cvs/my-cv" in _values(["render"], "cvs/")


def test_position1_prunes_bare_job_postings(monkeypatch):
    # a job posting with no optimized CVs is not a renderable target
    monkeypatch.setattr(
        cli_mod,
        "_load_collection",
        lambda name: [{"identifier": "acme"}] if name == "job-postings" else [],
    )
    assert _values(["render"], "job") == []


def test_position2_file_mode_offers_stdin_and_files(monkeypatch):
    monkeypatch.setattr(cli_mod, "_load_collection", lambda name: [])
    items = _items(["render", "cv"], "")
    assert "-" in [c.value for c in items]
    assert "file" in [c.type for c in items]


def test_position2_uri_mode_offers_nothing(monkeypatch):
    monkeypatch.setattr(cli_mod, "_load_collection", lambda name: [])
    assert _items(["render", "cvs/my-cv"], "") == []
