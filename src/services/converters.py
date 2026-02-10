import re
from typing import Any

from pydantic import BaseModel

from models import CurriculumVitae, CvTransformationPlan, JobPosting

URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


class MarkdownConverter:
    """Converts domain objects to markdown using type-specific composers."""

    def __init__(self):
        self._composers = {
            JobPosting: _compose_job_posting,
            CurriculumVitae: _compose_cv,
            CvTransformationPlan: _compose_transformation_plan,
        }

    def convert(self, data) -> str:
        """Convert a domain object or dict to markdown."""
        composer = self._composers.get(type(data))
        if composer:
            document = composer(data)
            return _render(document)

        if isinstance(data, BaseModel):
            return _render(data.model_dump())

        return _render(data)


def _compose_job_posting(job: JobPosting) -> dict:
    """Compose a job posting into a markdown-ready document structure."""
    if job.company and job.company.lower() != "not specified":
        title = f"{job.title} at {job.company}"
    else:
        title = job.title

    document: dict[str, Any] = {"_title": title}

    if job.url:
        document["original_posting"] = job.url

    if job.company and job.company.lower() != "not specified":
        document["company"] = job.company
    if job.industry:
        document["industry"] = job.industry
    if job.experience_level:
        document["experience_level"] = job.experience_level

    if job.description:
        document["description"] = job.description

    requirements = {}
    if job.education:
        requirements["education"] = job.education
    if job.years_experience:
        requirements["years_experience"] = job.years_experience
    if job.hard_requirements:
        requirements["must_have"] = job.hard_requirements
    if requirements:
        document["requirements"] = requirements

    skills = {}
    if job.technical_skills:
        skills["technical"] = job.technical_skills
    if job.soft_skills:
        skills["soft"] = job.soft_skills
    if job.preferred_skills:
        skills["preferred"] = job.preferred_skills
    if skills:
        document["skills"] = skills

    if job.responsibilities:
        document["responsibilities"] = job.responsibilities

    if job.keywords or job.tools_and_tech:
        ats = {}
        if job.keywords:
            ats["keywords"] = job.keywords
        if job.tools_and_tech:
            ats["tools_and_technologies"] = job.tools_and_tech
        document["ats_optimization"] = ats

    return document


def _compose_transformation_plan(plan: CvTransformationPlan) -> dict:
    """Compose a transformation plan into a markdown-ready document structure."""
    document: dict[str, Any] = {
        "_title": f"Transformation Plan: {plan.job_title} at {plan.company}"
    }

    alignment = {}
    if plan.matching_skills:
        alignment["matching_skills"] = plan.matching_skills
    if plan.missing_skills:
        alignment["missing_skills"] = plan.missing_skills
    if plan.transferable_skills:
        alignment["transferable_skills"] = plan.transferable_skills
    if alignment:
        document["alignment_analysis"] = alignment

    transformations = {}
    if plan.profession_update:
        transformations["profession_update"] = plan.profession_update
    if plan.core_expertise_updates:
        transformations["core_expertise_updates"] = plan.core_expertise_updates
    if plan.summary_updates:
        transformations["summary_updates"] = plan.summary_updates
    if plan.experience_updates:
        transformations["experience_updates"] = plan.experience_updates
    if transformations:
        document["transformations"] = transformations

    ats = {}
    if plan.keyword_insertions:
        ats["keyword_insertions"] = plan.keyword_insertions
    if plan.quantification_suggestions:
        ats["quantification_suggestions"] = plan.quantification_suggestions
    if ats:
        document["ats_optimization"] = ats

    if plan.evidence_sources:
        document["evidence_sources"] = plan.evidence_sources

    return document


def _compose_cv(cv: CurriculumVitae) -> dict:
    """Compose a CV into a markdown-ready document structure."""
    document: dict[str, Any] = {"_title": cv.name}

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
            document["contact"] = contact

    if cv.profession:
        document["profession"] = cv.profession
    if cv.core_expertise:
        document["core_expertise"] = cv.core_expertise
    if cv.summary_of_qualifications:
        document["summary"] = cv.summary_of_qualifications

    if cv.experience:
        document["experience"] = [
            {
                "title": exp.title,
                "company": exp.company,
                "location": exp.location,
                "dates": f"{exp.start_date} - {exp.end_date}",
                "responsibilities": exp.responsibilities,
            }
            for exp in cv.experience
        ]

    if cv.additional_experience:
        document["additional_experience"] = [
            {
                "title": exp.title,
                "company": exp.company,
                "dates": f"{exp.start_date} - {exp.end_date}",
            }
            for exp in cv.additional_experience
        ]

    if cv.education:
        document["education"] = [
            {
                "degree": edu.degree,
                "institution": edu.institution,
                "location": edu.location,
                "dates": f"{edu.start_date} - {edu.end_date}",
                "coursework": edu.coursework if edu.coursework else None,
            }
            for edu in cv.education
        ]

    if cv.areas_of_expertise:
        document["skills"] = {area.name: area.skills for area in cv.areas_of_expertise}

    if cv.languages:
        document["languages"] = {lang.language: lang.level for lang in cv.languages}

    return document


def _render(data: dict, level: int = 1) -> str:
    """Render a dict as markdown. Type-agnostic."""
    lines = []

    title = data.pop("_title", None) if isinstance(data, dict) else None
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
                parts.append(_render({"_title": sub_title, **item}, level=level + 1))
        return "\n".join(parts)

    if isinstance(value, dict):
        return f"{'#' * level} {name}\n\n{_render(value, level=level + 1)}"

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
