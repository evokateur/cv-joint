import yaml
import json
import subprocess
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, Type

from renderers.latex.template_env import get_tex_env


def render_latex(
    input_file: str,
    output_file: str,
    template_name: str,
    schema_class: Optional[Type[BaseModel]] = None,
    post_replace: Optional[dict] = None,
):
    """
    Render LaTeX from JSON/YAML data and template, with optional post-render replacements.

    Args:
        input_file: Path to input JSON or YAML file containing data
        output_file: Path to output LaTeX file
        template_name: Name of the template file in the templates directory
        schema_class: Optional Pydantic model class for validation
        post_replace: Optional dict of {placeholder: attribute_name} for post-render replacement
    """
    path = Path(input_file)
    with open(input_file) as f:
        if path.suffix.lower() == ".json":
            data = json.load(f)
        else:
            data = yaml.safe_load(f)

    if schema_class is not None:
        obj = schema_class(**data)
        obj_data = obj.model_dump()
    else:
        obj = None
        obj_data = data

    env = get_tex_env()
    template = env.get_template(template_name)
    rendered_tex = template.render(obj_data)

    if post_replace:
        for placeholder, attr in post_replace.items():
            value = getattr(obj, attr, None)
            if value and placeholder in rendered_tex:
                rendered_tex = rendered_tex.replace(placeholder, value)

    with open(output_file, "w") as f:
        f.write(rendered_tex)


def latex_to_pdf(tex_path: str) -> str:
    """Compile a .tex file to PDF using pdflatex.

    Args:
        tex_path: Path to the .tex file

    Returns:
        Path to the generated .pdf file
    """
    tex_file = Path(tex_path)
    output_directory = str(tex_file.parent)

    subprocess.run(
        [
            "pdflatex",
            "-interaction=nonstopmode",
            "-output-directory",
            output_directory,
            tex_path,
        ],
        capture_output=True,
        check=True,
    )

    pdf_path = tex_file.with_suffix(".pdf")
    if not pdf_path.exists():
        raise FileNotFoundError(f"pdflatex did not produce {pdf_path}")

    return str(pdf_path)
