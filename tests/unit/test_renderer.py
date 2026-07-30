import shutil

import pytest

from renderers.latex import RENDERERS, load_data, render_document

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
    "paragraphs": ["Interested in the xXposition role at xXcompany."],
}


def test_registry_types():
    assert set(RENDERERS) == {"cv", "cover-letter"}
    assert RENDERERS["cv"].template == "cv.tex"
    assert RENDERERS["cover-letter"].template == "cover-letter.tex"


def test_load_data_json(tmp_path):
    path = tmp_path / "data.json"
    path.write_text('{"a": 1}')
    assert load_data(str(path)) == {"a": 1}


def test_load_data_yaml(tmp_path):
    path = tmp_path / "data.yaml"
    path.write_text("a: 1\n")
    assert load_data(str(path)) == {"a": 1}


def test_render_document_tex_writes_source(tmp_path):
    out = tmp_path / "cover-letter.tex"
    render_document(COVER_LETTER, "cover-letter", fmt="tex", output_path=str(out))
    text = out.read_text()
    assert "FrobozzCo" in text and "xXcompany" not in text
    assert "Developer" in text and "xXposition" not in text


def test_render_document_unknown_type():
    with pytest.raises(ValueError, match="unknown type"):
        render_document(COVER_LETTER, "nope", fmt="tex", output_path="x.tex")


def test_render_document_unknown_format(tmp_path):
    with pytest.raises(ValueError, match="unknown format"):
        render_document(
            COVER_LETTER, "cover-letter", fmt="ps", output_path=str(tmp_path / "x")
        )


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex not installed")
def test_render_document_pdf_leaves_only_pdf(tmp_path):
    out = tmp_path / "cover-letter.pdf"
    render_document(COVER_LETTER, "cover-letter", fmt="pdf", output_path=str(out))
    assert out.exists()
    # temp-dir compile: destination dir holds only the .pdf, no aux/log/tex litter
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cover-letter.pdf"]
