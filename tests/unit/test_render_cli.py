import json

from click.testing import CliRunner

from ui.cli import main

COVER_LETTER = {
    "name": "Test Person",
    "contact": {
        "city": "Oakland",
        "state": "CA",
        "phone": "+1-555-000-0000",
        "email": "test@example.com",
    },
    "company": "FrobozzCo",
    "position": "Developer",
    "salutation": "Dear Hiring Manager,",
    "closing": "Sincerely,",
    "paragraphs": ["Interested in the xXposition role at xXcompany."],
}


def _data_file(tmp_path):
    path = tmp_path / "cover-letter.json"
    path.write_text(json.dumps(COVER_LETTER))
    return str(path)


def test_render_tex_to_output(tmp_path):
    out = tmp_path / "out.tex"
    result = CliRunner().invoke(
        main,
        ["render", "cover-letter", _data_file(tmp_path), "-f", "tex", "-o", str(out)],
    )
    assert result.exit_code == 0, result.output
    text = out.read_text()
    assert "FrobozzCo" in text and "xXcompany" not in text


def test_render_tex_to_stdout(tmp_path):
    result = CliRunner().invoke(
        main,
        ["render", "cover-letter", _data_file(tmp_path), "-f", "tex", "-o", "-"],
    )
    assert result.exit_code == 0, result.output
    assert "FrobozzCo" in result.output


def test_render_unknown_type_exits_nonzero(tmp_path):
    out = tmp_path / "out.tex"
    result = CliRunner().invoke(
        main,
        ["render", "nope", _data_file(tmp_path), "-f", "tex", "-o", str(out)],
    )
    assert result.exit_code != 0
    assert "unknown type" in result.output


def test_render_stdin_without_output_errors(tmp_path):
    result = CliRunner().invoke(
        main,
        ["render", "cover-letter", "-", "-f", "tex"],
        input=json.dumps(COVER_LETTER),
    )
    assert result.exit_code != 0
    assert "stdin" in result.output.lower()


def test_render_unrecognised_uri_errors():
    result = CliRunner().invoke(main, ["render", "not-a-uri"])
    assert result.exit_code != 0
    assert "unrecognised URI" in result.output


def test_render_too_many_args_errors(tmp_path):
    result = CliRunner().invoke(
        main, ["render", "cv", str(tmp_path / "a"), "extra"]
    )
    assert result.exit_code != 0
