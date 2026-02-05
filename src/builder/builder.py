import yaml
import json
from pathlib import Path
from builder.template_env import get_tex_env
from models.schema import CurriculumVitae, CoverLetter


def build_cv(input_file: str, output_file: str, template_name: str = "cv.tex"):
    """Build CV from JSON/YAML data and LaTeX template

    Args:
        input_file: Path to input JSON or YAML file containing CV data
        output_file: Path to output LaTeX file
        template_name: Name of the template file in the templates directory

    Raises:
        ValidationError: If CV data does not match CurriculumVitae schema
    """
    path = Path(input_file)
    with open(input_file) as f:
        if path.suffix.lower() == ".json":
            data = json.load(f)
        else:
            data = yaml.safe_load(f)

    cv = CurriculumVitae(**data)

    env = get_tex_env()
    template = env.get_template(template_name)

    rendered_tex = template.render(cv.model_dump())

    with open(output_file, "w") as f:
        f.write(rendered_tex)


def build_cover_letter(input_file: str, output_file: str):
    """Build cover letter from JSON/YAML data and LaTeX template

    Cover letters require special handling for position and company placeholders
    that are replaced after template rendering.

    Args:
        input_file: Path to input JSON or YAML file containing cover letter data
        output_file: Path to output LaTeX file

    Raises:
        ValidationError: If cover letter data does not match CoverLetter schema
    """
    path = Path(input_file)
    with open(input_file) as f:
        if path.suffix.lower() == ".json":
            data = json.load(f)
        else:
            data = yaml.safe_load(f)

    cover_letter = CoverLetter(**data)
    cover_letter_data = cover_letter.model_dump()

    env = get_tex_env()
    template = env.get_template("cover-letter.tex")

    rendered_tex = template.render(cover_letter_data)

    final_tex = rendered_tex.replace("xXposition", cover_letter.position).replace(
        "xXcompany", cover_letter.company
    )

    with open(output_file, "w") as f:
        f.write(final_tex)
