"""One description per entity type, consulted instead of dispatching on type."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel

from models import (
    CoverLetter,
    CoverLetterRecord,
    CurriculumVitae,
    CurriculumVitaeRecord,
    JobPosting,
    JobPostingRecord,
    OptimizedCvRecord,
)
from repositories.filesystem import FileSystemRepository, content_filename


def _slugify(text: str) -> str:
    """Lowercase, drop punctuation, and hyphenate whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")


def _slugify_job(data: dict[str, Any]) -> str:
    if data["company"].lower() == "not specified":
        return _slugify(data["title"])
    return f"{_slugify(data['company'])}-{_slugify(data['title'])}"


@dataclass(frozen=True)
class EntityType:
    """An entity collection: its models, listing summary and repository operations.

    Repository operations are unbound FileSystemRepository methods, called with
    the repository followed by the entity's key.
    """

    collection: str
    record_model: type[BaseModel]
    content_model: type[BaseModel]
    summary_fields: tuple[str, ...]
    get_record: Callable[..., Any]
    get_records: Callable[[FileSystemRepository], list]
    add: Callable[..., Any]
    update_record: Callable[..., Any]
    remove: Callable[..., bool]
    rename: Callable[..., Any]
    child_collections: tuple[str, ...] = ()
    loadable: bool = False
    renderable: bool = False
    default_slug: Callable[[dict[str, Any]], str] | None = None

    @property
    def content_file(self) -> str:
        return content_filename(self.content_model)

    def summary(self, content: BaseModel) -> dict[str, Any]:
        """The record's listing fields, taken from the content."""
        return {field: getattr(content, field) for field in self.summary_fields}

    def key(self, record) -> tuple[str, ...]:
        """The identifiers that address record in the repository."""
        return (record.identifier,)

    def key_of(self, parsed: dict[str, str]) -> tuple[str, ...]:
        """The repository key of a URI parsed by parse_uri."""
        return (parsed["identifier"],)

    def uri(self, record) -> str:
        return f"{self.collection}/{record.identifier}"


@dataclass(frozen=True)
class OptimizedCvType(EntityType):
    """Optimized CVs are nested under their posting: job-postings/{posting}/cvs/{id}."""

    def key(self, record) -> tuple[str, ...]:
        return (record.job_posting_identifier, record.identifier)

    def key_of(self, parsed: dict[str, str]) -> tuple[str, ...]:
        return (parsed["job_posting_identifier"], parsed["identifier"])

    def uri(self, record) -> str:
        return f"job-postings/{record.job_posting_identifier}/cvs/{record.identifier}"


OPTIMIZED_CVS = "optimized-cvs"

ENTITY_TYPES: dict[str, EntityType] = {
    entity_type.collection: entity_type
    for entity_type in (
        EntityType(
            collection="job-postings",
            record_model=JobPostingRecord,
            content_model=JobPosting,
            summary_fields=("url", "company", "title", "experience_level"),
            get_record=FileSystemRepository.get_job_posting_record,
            get_records=lambda repository: repository.get_job_posting_records(all=True),
            add=FileSystemRepository.add_job_posting,
            update_record=FileSystemRepository.update_job_posting_record,
            remove=FileSystemRepository.remove_job_posting,
            rename=FileSystemRepository.rename_job_posting,
            child_collections=("cvs",),
            loadable=True,
            default_slug=_slugify_job,
        ),
        EntityType(
            collection="cvs",
            record_model=CurriculumVitaeRecord,
            content_model=CurriculumVitae,
            summary_fields=("name", "profession"),
            get_record=FileSystemRepository.get_cv_record,
            get_records=FileSystemRepository.get_cv_records,
            add=FileSystemRepository.add_cv,
            update_record=FileSystemRepository.update_cv_record,
            remove=FileSystemRepository.remove_cv,
            rename=FileSystemRepository.rename_cv,
            loadable=True,
            renderable=True,
            default_slug=lambda data: _slugify(data["profession"]),
        ),
        OptimizedCvType(
            collection=OPTIMIZED_CVS,
            record_model=OptimizedCvRecord,
            content_model=CurriculumVitae,
            summary_fields=("name", "profession"),
            get_record=FileSystemRepository.get_optimized_cv_record,
            get_records=FileSystemRepository.get_optimized_cv_records,
            add=FileSystemRepository.add_optimized_cv,
            update_record=FileSystemRepository.update_cv_record,
            remove=FileSystemRepository.remove_optimized_cv,
            rename=FileSystemRepository.rename_optimized_cv,
            loadable=True,
            renderable=True,
        ),
        EntityType(
            collection="cover-letters",
            record_model=CoverLetterRecord,
            content_model=CoverLetter,
            summary_fields=("name", "company", "position"),
            get_record=FileSystemRepository.get_cover_letter_record,
            get_records=FileSystemRepository.get_cover_letter_records,
            add=FileSystemRepository.add_cover_letter,
            update_record=FileSystemRepository.update_cover_letter_record,
            remove=FileSystemRepository.remove_cover_letter,
            rename=FileSystemRepository.rename_cover_letter,
            renderable=True,
        ),
    )
}

# Collections addressed directly by {collection}/{identifier}.
TOP_LEVEL_COLLECTIONS = tuple(
    collection for collection in ENTITY_TYPES if collection != OPTIMIZED_CVS
)


def entity_type_of(record) -> EntityType:
    """The entity type whose records are of record's class."""
    return next(
        entity_type
        for entity_type in ENTITY_TYPES.values()
        if type(record) is entity_type.record_model
    )
