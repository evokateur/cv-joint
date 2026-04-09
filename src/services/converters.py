import re
from pathlib import Path
from typing import Optional

import yaml
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel

from models import CurriculumVitae, CvTransformationPlan, JobPosting

URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "markdown"


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

    def convert_job_posting(self, job: JobPosting, record: Optional[BaseModel] = None) -> str:
        template = self._env.get_template("job-posting.md")
        frontmatter = _render_frontmatter(record) if record else ""
        return template.render(frontmatter=frontmatter, job=job)

    def convert_cv(self, cv: CurriculumVitae, record: Optional[BaseModel] = None) -> str:
        template = self._env.get_template("cv.md")
        frontmatter = _render_frontmatter(record) if record else ""
        return template.render(frontmatter=frontmatter, cv=cv)

    def convert_transformation_plan(
        self, plan: CvTransformationPlan, record: Optional[BaseModel] = None
    ) -> str:
        template = self._env.get_template("transformation-plan.md")
        frontmatter = _render_frontmatter(record) if record else ""
        return template.render(frontmatter=frontmatter, plan=plan)

    def convert(self, domain_object) -> str:
        """Convert a domain object to markdown without frontmatter (for previews)."""
        if isinstance(domain_object, JobPosting):
            return self.convert_job_posting(domain_object)
        if isinstance(domain_object, CurriculumVitae):
            return self.convert_cv(domain_object)
        if isinstance(domain_object, CvTransformationPlan):
            return self.convert_transformation_plan(domain_object)
        raise TypeError(f"No markdown template for {type(domain_object).__name__}")
