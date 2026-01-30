import re
from typing import Any, Callable, Union

from pydantic import BaseModel

from models import CurriculumVitae, JobPosting

URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


def _default_presenter(model: BaseModel) -> dict:
    """Bare minimum presenter - just convert to dict."""
    return model.model_dump()


def _present_job_posting(job: JobPosting) -> dict:
    """Present JobPosting for readable markdown."""
    result = {}

    # Link to original posting
    if job.url:
        result["original_posting"] = job.url

    # Basic info (title omitted - it's in the document header)
    if job.company and job.company.lower() != "not specified":
        result["company"] = job.company
    if job.industry:
        result["industry"] = job.industry
    if job.experience_level:
        result["experience_level"] = job.experience_level

    # Description
    if job.description:
        result["description"] = job.description

    # Requirements grouped
    requirements = {}
    if job.education:
        requirements["education"] = job.education
    if job.years_experience:
        requirements["years_experience"] = job.years_experience
    if job.hard_requirements:
        requirements["must_have"] = job.hard_requirements
    if requirements:
        result["requirements"] = requirements

    # Skills grouped
    skills = {}
    if job.technical_skills:
        skills["technical"] = job.technical_skills
    if job.soft_skills:
        skills["soft"] = job.soft_skills
    if job.preferred_skills:
        skills["preferred"] = job.preferred_skills
    if skills:
        result["skills"] = skills

    # Responsibilities
    if job.responsibilities:
        result["responsibilities"] = job.responsibilities

    # ATS info
    if job.keywords or job.tools_and_tech:
        ats = {}
        if job.keywords:
            ats["keywords"] = job.keywords
        if job.tools_and_tech:
            ats["tools_and_technologies"] = job.tools_and_tech
        result["ats_optimization"] = ats

    return result


def _present_cv(cv: CurriculumVitae) -> dict:
    """Present CurriculumVitae for readable markdown."""
    result = {}

    # Contact info (name omitted - it's in the document header)
    if cv.contact:
        contact = {}
        if cv.contact.email:
            contact["email"] = cv.contact.email
        if cv.contact.phone:
            contact["phone"] = cv.contact.phone
        if cv.contact.city and cv.contact.state:
            contact["location"] = f"{cv.contact.city}, {cv.contact.state}"
        if cv.contact.linkedin:
            contact["linkedin"] = cv.contact.linkedin
        if cv.contact.github:
            contact["github"] = cv.contact.github
        if contact:
            result["contact"] = contact

    # Professional summary
    if cv.profession:
        result["profession"] = cv.profession
    if cv.core_expertise:
        result["core_expertise"] = cv.core_expertise
    if cv.summary_of_qualifications:
        result["summary"] = cv.summary_of_qualifications

    # Experience
    if cv.experience:
        result["experience"] = [
            {
                "title": exp.title,
                "company": exp.company,
                "location": exp.location,
                "dates": f"{exp.start_date} - {exp.end_date}",
                "responsibilities": exp.responsibilities,
            }
            for exp in cv.experience
        ]

    # Additional experience (condensed)
    if cv.additional_experience:
        result["additional_experience"] = [
            {
                "title": exp.title,
                "company": exp.company,
                "dates": f"{exp.start_date} - {exp.end_date}",
            }
            for exp in cv.additional_experience
        ]

    # Education
    if cv.education:
        result["education"] = [
            {
                "degree": edu.degree,
                "institution": edu.institution,
                "location": edu.location,
                "dates": f"{edu.start_date} - {edu.end_date}",
                "coursework": edu.coursework if edu.coursework else None,
            }
            for edu in cv.education
        ]

    # Skills by area
    if cv.areas_of_expertise:
        result["skills"] = {
            area.name: area.skills
            for area in cv.areas_of_expertise
        }

    # Languages
    if cv.languages:
        result["languages"] = {
            lang.language: lang.level
            for lang in cv.languages
        }

    return result


def _get_presenter(model: BaseModel) -> Callable[[BaseModel], dict]:
    """Return the appropriate presenter for a model type."""
    presenters = {
        JobPosting: _present_job_posting,
        CurriculumVitae: _present_cv,
    }
    return presenters.get(type(model), _default_presenter)


def to_markdown(
    data: Union[dict, BaseModel],
    title: str | None = None,
    level: int = 1,
) -> str:
    """
    Convert any dict or Pydantic model to markdown.

    Args:
        data: Dict or Pydantic model to convert
        title: Optional title for the document
        level: Starting header level (1 = #, 2 = ##, etc.)

    Returns:
        Markdown string representation
    """
    if isinstance(data, BaseModel):
        presenter = _get_presenter(data)
        data = presenter(data)

    lines = []
    if title:
        lines.append(f"{'#' * level} {title}\n")
        level += 1

    for key, value in data.items():
        heading = _key_to_heading(key)
        formatted = _format_field(heading, value, level)
        if formatted:
            lines.append(formatted)

    return "\n".join(lines)


def _key_to_heading(key: str) -> str:
    """Convert snake_case to Title Case."""
    return key.replace("_", " ").title()


def _format_field(name: str, value: Any, level: int) -> str:
    """Format a single field as markdown."""
    if value is None or value == "" or value == []:
        return ""

    if isinstance(value, str):
        value = _linkify_urls(value)
        if len(value) < 80 and "\n" not in value:
            return f"**{name}:** {value}\n"
        return f"**{name}:**\n\n{value}\n"

    if isinstance(value, list):
        if not value:
            return ""
        if all(isinstance(item, str) for item in value):
            items = "\n".join(f"- {_linkify_urls(item)}" for item in value)
            return f"**{name}:**\n\n{items}\n"
        parts = [f"{'#' * level} {name}\n"]
        for i, item in enumerate(value):
            if isinstance(item, dict):
                sub_title = _extract_title(item) or f"Item {i + 1}"
                parts.append(to_markdown(item, title=sub_title, level=level + 1))
        return "\n".join(parts)

    if isinstance(value, dict):
        return f"{'#' * level} {name}\n\n{to_markdown(value, level=level + 1)}"

    return f"**{name}:** {value}\n"


def _linkify_urls(text: str) -> str:
    """Convert URLs in text to markdown links."""
    def replace(match):
        url = match.group(0)
        display = url if len(url) < 60 else url[:57] + "..."
        return f"[{display}]({url})"
    return URL_PATTERN.sub(replace, text)


def _extract_title(obj: dict) -> str | None:
    """Extract a reasonable title from an object."""
    for field in ("title", "name", "company", "degree", "language"):
        if field in obj and obj[field]:
            return obj[field]
    return None
