import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import yaml

from renderers.latex.registry import RENDERERS
from renderers.latex.template_env import get_tex_env

TEMPLATES_DIR = str(Path(__file__).parents[3] / "templates")


def load_data(input_file: str) -> dict:
    """Load a data dict from a JSON or YAML file."""
    path = Path(input_file)
    with open(input_file) as f:
        if path.suffix.lower() == ".json":
            return json.load(f)
        return yaml.safe_load(f)


def render_tex(data: dict, template_name: str) -> str:
    """Render a template to a TeX string from a prepared data dict."""
    env = get_tex_env(TEMPLATES_DIR)
    return env.get_template(template_name).render(data)


def tex_to_pdf(tex_source: str, output_pdf: str) -> str:
    """Compile TeX source to a PDF, compiling in a temp dir so only the .pdf surfaces.

    pdflatex writes .tex/.aux/.log alongside the .pdf; running it in a throwaway
    directory keeps those intermediates out of the destination.

    Args:
        tex_source: The full TeX document to compile
        output_pdf: Destination path for the compiled PDF

    Returns:
        The destination path.
    """
    destination = Path(output_pdf)
    jobname = destination.stem

    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / f"{jobname}.tex").write_text(tex_source)
        subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-output-directory",
                tmp,
                "-jobname",
                jobname,
                str(Path(tmp) / f"{jobname}.tex"),
            ],
            capture_output=True,
            check=True,
        )
        produced = Path(tmp) / f"{jobname}.pdf"
        if not produced.exists():
            raise FileNotFoundError(f"pdflatex did not produce {produced}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(produced), str(destination))

    return str(destination)


def render_document(
    data: dict,
    type_name: str,
    fmt: str = "pdf",
    output_path: Optional[str] = None,
    template: Optional[str] = None,
) -> str:
    """Render a registered document type to a file, in the given format.

    Uses the document type to choose a default template, then writes the .tex
    (fmt="tex") or compiles a .pdf in a temp dir (fmt="pdf").

    Args:
        data: Raw data dict for the document
        type_name: A key in the renderer registry (e.g. "cv")
        fmt: "pdf" or "tex"
        output_path: Destination file path
        template: Optional template name overriding the type's default

    Returns:
        The destination path.
    """
    try:
        spec = RENDERERS[type_name]
    except KeyError:
        raise ValueError(f"unknown type: {type_name!r}") from None

    tex_source = render_tex(data, template or spec.template)

    if fmt == "tex":
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(tex_source)
        return str(destination)
    if fmt == "pdf":
        return tex_to_pdf(tex_source, output_path)
    raise ValueError(f"unknown format: {fmt!r}")
