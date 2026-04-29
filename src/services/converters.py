import re
from pathlib import Path
from typing import Optional

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pydantic import BaseModel

from models import CurriculumVitae, CvTransformationPlan, JobPosting

URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "markdown"


def _to_kebab_case(name: str) -> str:
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1-\2", s1).lower()


def _linkify(text: str) -> str:
    def replace(match):
        url = match.group(0)
        display = url if len(url) < 60 else url[:57] + "..."
        return f"[{display}]({url})"

    return URL_PATTERN.sub(replace, text)


def _render_frontmatter(record: BaseModel) -> str:
    data = record.model_dump(mode="json")
    return f"---\n{yaml.dump(data, default_flow_style=False, allow_unicode=True)}---\n"


class MarkdownConverter:
    """Converts domain objects to markdown using Jinja2 templates."""

    def __init__(self, templates_dir: str | None = None):
        loader = FileSystemLoader(templates_dir or str(_TEMPLATES_DIR))
        self._env = Environment(
            loader=loader,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        self._env.filters["linkify"] = _linkify

    def convert(self, obj: BaseModel, record: Optional[BaseModel] = None) -> Optional[str]:
        """Convert a domain object to markdown. Returns None if no template exists."""
        template_name = _to_kebab_case(type(obj).__name__) + ".md"
        try:
            template = self._env.get_template(template_name)
        except TemplateNotFound:
            return None
        frontmatter = _render_frontmatter(record) if record else ""
        return template.render(frontmatter=frontmatter, obj=obj)

    def convert_job_posting(self, job: JobPosting, record: Optional[BaseModel] = None) -> Optional[str]:
        return self.convert(job, record)

    def convert_cv(self, cv: CurriculumVitae, record: Optional[BaseModel] = None) -> Optional[str]:
        return self.convert(cv, record)

    def convert_transformation_plan(
        self, plan: CvTransformationPlan, record: Optional[BaseModel] = None
    ) -> Optional[str]:
        return self.convert(plan, record)
