from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime
from typing import Any, Callable, Optional

from config.root import get_settings
from models import (
    CurriculumVitae,
    CurriculumVitaeRecord,
    JobPosting,
    JobPostingRecord,
    OptimizedCvRecord,
)
from services.analyzers import JobPostingAnalyzer
from services.analyzers import CvAnalyzer
from services.analyzers import CvOptimizer
from .converters import MarkdownConverter, insert_json_as_frontmatter
from .exporters import MarkdownExporter, read_transformation_plan
from repositories import DocumentExistsError, FileSystemRepository
from services.addressing import (
    parse_document_uri,
    parse_uri,
    resolve_record,
    validate_filename,
    validate_identifier,
)
from services.entity_types import (
    ENTITY_TYPES,
    OPTIMIZED_CVS,
    TOP_LEVEL_COLLECTIONS,
    entity_type_of,
)
from renderers.latex import render_tex, tex_to_pdf

# The named output holding the entity content in a producer's outputs, for each
# collection load accepts.
PRODUCER_OUTPUT_PRIMARY_FILES = {
    collection: entity_type.content_file
    for collection, entity_type in ENTITY_TYPES.items()
    if entity_type.loadable
}


def _document_bytes(content: Any) -> bytes:
    """Encode a named output: strings as UTF-8 text, anything else as JSON."""
    if isinstance(content, str):
        return content.encode()
    return json.dumps(content, indent=2).encode()


def _parse_new_entity_uri(entity_uri: str) -> dict[str, str]:
    """Parse an entity URI that add can create, by its shape alone."""
    try:
        parsed = parse_uri(entity_uri)
    except ValueError:
        raise ValueError(f"Cannot add to {entity_uri}") from None
    return parsed


def _next_identifier(identifier: str, exists: Callable[[str], Any]) -> str:
    stripped = re.sub(r"-\d+$", "", identifier)
    base = stripped if stripped != identifier and exists(stripped) else identifier
    counter = 2
    candidate = f"{base}-{counter}"
    while exists(candidate):
        counter += 1
        candidate = f"{base}-{counter}"
    return candidate


class ApplicationService:
    """
    Application service for CV Joint operations.
    """

    def __init__(
        self,
        repository: Optional[FileSystemRepository] = None,
        cv_analyzer: Optional[CvAnalyzer] = None,
        job_posting_analyzer: Optional[JobPostingAnalyzer] = None,
        cv_optimizer: Optional[CvOptimizer] = None,
    ):
        self.job_posting_analyzer = job_posting_analyzer or JobPostingAnalyzer()
        self.cv_analyzer = cv_analyzer or CvAnalyzer()
        self.cv_optimizer = cv_optimizer or CvOptimizer()
        if repository is None:
            settings = get_settings()
            repository = FileSystemRepository(
                data_dir=settings.repositories.filesystem.data_dir
            )
        self.repository = repository
        self.markdown_converter = MarkdownConverter()
        self.markdown_exporter = MarkdownExporter(
            self.repository, self.markdown_converter
        )

    def list_locations(self) -> list[str]:
        """Return locations present in posting records."""
        return sorted(
            {
                record.location
                for record in self.repository.get_job_posting_records(all=True)
                if record.location is not None
            }
        )

    def add(self, entity_uri: str, data: dict[str, Any] | str) -> str:
        """Create exactly the entity at entity_uri from a dict or JSON text. Returns its URI."""
        return self._add(entity_uri, data)

    def _add(
        self,
        entity_uri: str,
        data: dict[str, Any] | str,
        *,
        base_cv_identifier: str | None = None,
    ) -> str:
        """Create an entity, recording the base CV an optimized CV came from."""
        if isinstance(data, str):
            data = json.loads(data)
        if not isinstance(data, dict):
            raise ValueError("Entity content must be a JSON object")
        parsed = _parse_new_entity_uri(entity_uri)
        entity_type = ENTITY_TYPES[parsed["collection"]]
        if entity_type.collection == OPTIMIZED_CVS:
            posting = parsed["job_posting_identifier"]
            parent = resolve_record(self.repository, f"job-postings/{posting}")
        identifier = validate_identifier(parsed["identifier"])
        if self.object_exists(entity_uri):
            raise ValueError(f"Already exists: {entity_uri}")
        content = entity_type.content_model(**data)
        now = datetime.now()
        fields = {
            "identifier": identifier,
            **entity_type.summary(content),
            "created_at": now,
            "updated_at": now,
        }
        if entity_type.collection == OPTIMIZED_CVS:
            record = OptimizedCvRecord(
                **fields,
                job_posting_identifier=posting,
                base_cv_identifier=base_cv_identifier,
                job_title=parent.title,
                company=parent.company,
            )
            record = self.repository.add_optimized_cv(parent, record, content)
        else:
            record = entity_type.add(
                self.repository, entity_type.record_model(**fields), content
            )
        return self._record_uri(record)

    def load(self, entity_uri: str, outputs: dict[str, Any] | str) -> str:
        """Create exactly the entity at entity_uri from named outputs. Returns its URI."""
        if isinstance(outputs, str):
            try:
                outputs = json.loads(outputs)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid named outputs: {error}") from None
        if not isinstance(outputs, dict):
            raise ValueError("Named outputs must be a JSON object")
        primary_file = self._validate_load(entity_uri, outputs)
        base_cv_identifier = self._base_cv_identifier(outputs.get("base_cv_uri"))
        try:
            documents = {
                filename: _document_bytes(content)
                for filename, content in outputs.items()
                if filename not in (primary_file, "base_cv_uri")
            }
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Named outputs must be JSON-compatible: {error}"
            ) from error
        entity_uri = self._add(
            entity_uri, outputs[primary_file], base_cv_identifier=base_cv_identifier
        )
        for filename, content in documents.items():
            self.add_document(f"{entity_uri}/{filename}", content)
        return entity_uri

    def _require_record(self, uri: Any, record_type: type, kind: str):
        """The record of the existing entity of record_type that uri names."""
        try:
            record = resolve_record(self.repository, uri)
        except (AttributeError, ValueError):
            record = None
        if not isinstance(record, record_type):
            raise ValueError(f"Not an existing {kind}: {uri}")
        return record

    def _base_cv_identifier(self, base_cv_uri: Any) -> str | None:
        """Identifier of the existing base CV that base_cv_uri names, if any."""
        if base_cv_uri is None:
            return None
        try:
            record = self._require_record(base_cv_uri, CurriculumVitaeRecord, "base CV")
        except ValueError as error:
            raise ValueError(f"base_cv_uri: {error}") from None
        return record.identifier

    def _validate_load(self, entity_uri: str, outputs: dict[str, Any]) -> str:
        """Reject named outputs that load can't write in full."""
        try:
            collection = parse_uri(entity_uri)["collection"]
        except ValueError:
            collection = None
        if collection not in PRODUCER_OUTPUT_PRIMARY_FILES:
            raise ValueError(f"Cannot load into {entity_uri}")
        primary_file = PRODUCER_OUTPUT_PRIMARY_FILES[collection]
        if primary_file not in outputs:
            raise ValueError(f"Missing {primary_file}")
        for filename in outputs:
            validate_filename(filename)
        return primary_file

    def update(self, entity_uri: str, data: dict[str, Any] | str) -> str:
        """Replace entity content and refresh its listing record."""
        if self._select_records(entity_uri) is not None:
            raise ValueError(
                f"Cannot update collection, location or view: {entity_uri}"
            )
        record = self._entity_record(entity_uri)
        if isinstance(data, str):
            data = json.loads(data)
        if not isinstance(data, dict):
            raise ValueError("Entity content must be a JSON object")
        entity_type = entity_type_of(record)
        content = entity_type.content_model(**data)
        replacement = record.model_copy(
            update={**entity_type.summary(content), "updated_at": datetime.now()}
        )
        self.repository.save_object(record, content)
        entity_type.update_record(self.repository, replacement)
        return self._record_uri(record)

    def get(self, target: str, *, recursive=False, query=None):
        """Read content or select collection records by logical address."""
        records = self._select_records(target, recursive=recursive, query=query)
        if records is not None:
            return records
        record = self._entity_record(target)
        content = self.repository.load_object(
            record, entity_type_of(record).content_model
        )
        if content is None:
            raise FileNotFoundError(f"Content not found: {target}")
        return content

    def _select_records(self, target: str, *, recursive=False, query=None):
        """Select collection records, or return None for an exact target."""
        parts = target.strip("/").split("/")
        if parts == ["job-postings"] or (
            len(parts) == 2
            and parts[0] == "job-postings"
            and parts[1] in self.list_locations()
        ):
            location = parts[1] if len(parts) == 2 and not recursive else None
            records = self.repository.get_job_posting_records(
                location=location, all=recursive
            )
        elif len(parts) == 1 and parts[0] in TOP_LEVEL_COLLECTIONS:
            records = ENTITY_TYPES[parts[0]].get_records(self.repository)
        elif parts == ["optimized-cvs"] or (
            len(parts) == 2
            and parts[0] == "optimized-cvs"
            and parts[1] in self.list_locations()
        ):
            location = parts[1] if len(parts) == 2 and not recursive else None
            parents = {
                record.identifier
                for record in self.repository.get_job_posting_records(
                    location=location, all=recursive
                )
            }
            records = [
                record
                for record in self.repository.get_optimized_cv_records()
                if record.job_posting_identifier in parents
            ]
        elif len(parts) == 3 and parts[0] == "job-postings" and parts[2] == "cvs":
            resolve_record(self.repository, f"job-postings/{parts[1]}")
            records = self.repository.get_optimized_cv_records(parts[1])
        else:
            return None
        return [
            record
            for record in records
            if not query or query.casefold() in record.model_dump_json().casefold()
        ]

    def list(self, target: str, *, recursive=False, query=None) -> list[str]:
        """Name selected records, or an entity's documents and child collections."""
        records = self._select_records(target, recursive=recursive, query=query)
        if records is not None:
            return [self._record_uri(record) for record in records]
        record = self._entity_record(target)
        uri = self._record_uri(record)
        uris = [
            f"{uri}/{filename}" for filename in self.repository.list_documents(record)
        ]
        uris.extend(
            f"{uri}/{child}" for child in entity_type_of(record).child_collections
        )
        return uris

    def _entity_record(self, target: str):
        if target.strip("/").split("/")[0] not in TOP_LEVEL_COLLECTIONS:
            raise ValueError(f"Unrecognised target: {target}")
        return resolve_record(self.repository, target)

    def remove_document(self, document_uri: str) -> str:
        """Remove a document without changing its entity's record."""
        address = parse_document_uri(document_uri)
        if address is None:
            raise ValueError(f"Unrecognised document URI: {document_uri}")
        entity_uri, filename = address
        validate_filename(filename)
        record = self._entity_record(entity_uri)
        self.repository.remove_document(record, filename)
        return f"{self._record_uri(record)}/{filename}"

    def rename_document(self, document_uri: str, new_filename: str) -> str:
        """Rename a document without interpreting its bytes or changing its record."""
        address = parse_document_uri(document_uri)
        if address is None:
            raise ValueError(f"Unrecognised document URI: {document_uri}")
        entity_uri, filename = address
        validate_filename(filename)
        validate_filename(new_filename)
        new_uri = f"{entity_uri}/{new_filename}"
        if parse_document_uri(new_uri) is None:
            raise ValueError(f"Not a document address: {new_uri}")
        record = self._entity_record(entity_uri)
        self.repository.rename_document(record, filename, new_filename)
        return f"{self._record_uri(record)}/{new_filename}"

    def update_document(self, document_uri: str, content: bytes) -> str:
        """Replace a document's bytes without changing its entity's record."""
        address = parse_document_uri(document_uri)
        if address is None:
            raise ValueError(f"Unrecognised document URI: {document_uri}")
        entity_uri, filename = address
        validate_filename(filename)
        record = self._entity_record(entity_uri)
        self.repository.update_document(record, filename, content)
        return f"{self._record_uri(record)}/{filename}"

    def get_document(self, document_uri: str) -> bytes:
        """Read an entity's document without decoding or transforming it."""
        address = parse_document_uri(document_uri)
        if address is None:
            raise ValueError(f"Unrecognised document URI: {document_uri}")
        entity_uri, filename = address
        record = self._entity_record(entity_uri)
        return self.repository.load_document_bytes(record, filename)

    def complete_add_destinations(self, incomplete: str) -> list[str]:
        """Complete add destinations: collection prefixes and entities, ending in '/'."""
        entities = {f"{self._record_uri(record)}/" for record in self._entity_records()}
        candidates = self._collection_prefixes().keys() | entities
        return sorted(
            candidate for candidate in candidates if candidate.startswith(incomplete)
        )

    def complete_load_destinations(self, incomplete: str) -> list[str]:
        """Complete load destinations: loadable collection prefixes ending in '/'."""
        return sorted(
            prefix
            for prefix, collection in self._collection_prefixes().items()
            if collection in PRODUCER_OUTPUT_PRIMARY_FILES
            and prefix.startswith(incomplete)
        )

    def _collection_prefixes(self) -> dict[str, str]:
        """Writable collections, keyed by URI prefix ending in '/'."""
        postings = self.repository.get_job_posting_records(all=True)
        return {
            f"{collection}/": collection for collection in TOP_LEVEL_COLLECTIONS
        } | {
            f"job-postings/{record.identifier}/cvs/": OPTIMIZED_CVS
            for record in postings
        }

    def _entity_records(self) -> list:
        """Records of every entity in every location."""
        return [
            record
            for entity_type in ENTITY_TYPES.values()
            for record in entity_type.get_records(self.repository)
        ]

    def complete_targets(self, incomplete: str) -> list[str]:
        """Complete logical reading targets across every location."""
        candidates = set(ENTITY_TYPES)
        for location in self.list_locations():
            candidates.update((f"job-postings/{location}", f"optimized-cvs/{location}"))
        for record in self._entity_records():
            uri = self._record_uri(record)
            candidates.add(uri)
            candidates.update(
                f"{uri}/{filename}"
                for filename in self.repository.list_documents(record)
            )
            candidates.update(
                f"{uri}/{child}" for child in entity_type_of(record).child_collections
            )
        return sorted(
            candidate for candidate in candidates if candidate.startswith(incomplete)
        )

    def complete_render_targets(self, incomplete: str) -> list[str]:
        """Complete stored CV and cover-letter URIs suitable for rendering."""
        return sorted(
            uri
            for record in self._entity_records()
            if entity_type_of(record).renderable
            if (uri := self._record_uri(record)).startswith(incomplete)
        )

    @staticmethod
    def _record_uri(record) -> str:
        return entity_type_of(record).uri(record)

    def object_exists(self, uri: str) -> bool:
        """Whether an object exists at uri. The collision check, keyed on the URI.

        Handles object URIs only (job-postings/{id}, cvs/{id},
        cover-letters/{id}, job-postings/{id}/cvs/{id}). Anything else — an
        unparseable or document URI — is reported as not existing.
        """
        try:
            parsed = parse_uri(uri)
        except ValueError:
            return False
        entity_type = ENTITY_TYPES[parsed["collection"]]
        record = entity_type.get_record(self.repository, *entity_type.key_of(parsed))
        return (
            record is not None
            and self.repository.load_object(record, entity_type.content_model)
            is not None
        )

    def uniquify_entity_uri(self, new_uri: str) -> str:
        """new_uri when it's free, or with a -N suffix when it's taken. Reserves nothing."""
        prefix, terminal = new_uri.rsplit("/", 1)

        def exists(identifier: str) -> bool:
            return self.object_exists(f"{prefix}/{identifier}")

        if not exists(terminal):
            return new_uri
        return f"{prefix}/{_next_identifier(terminal, exists)}"

    def generate_default_entity_uri(
        self, collection_uri: str, data: dict[str, Any]
    ) -> str | None:
        """A free entity URI in collection_uri derived from the content's fields.

        None when the collection has no default identifier defined.
        """
        entity_type = ENTITY_TYPES.get(collection_uri)
        if entity_type is None or entity_type.default_slug is None:
            return None
        return self.uniquify_entity_uri(
            f"{collection_uri}/{entity_type.default_slug(data)}"
        )

    def analyze_job_posting_url(
        self, source_url: str, *, url: str | None = None
    ) -> dict[str, Any]:
        """Fetch source_url and analyze its content as a job posting.

        The posting's url is url when given, otherwise source_url. The fetched
        content lives in a context-managed temp file for the duration of the
        analysis, then is cleaned up automatically.
        """
        import requests

        resp = requests.get(source_url, timeout=30)
        resp.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".html") as tmp:
            tmp.write(resp.content)
            tmp.flush()
            posting = self.job_posting_analyzer.analyze(tmp.name)
        posting = posting.model_copy(update={"url": url or source_url})
        return {
            PRODUCER_OUTPUT_PRIMARY_FILES["job-postings"]: posting.model_dump(
                mode="json"
            )
        }

    def analyze_job_posting(
        self, content: str, *, url: str | None = None
    ) -> dict[str, Any]:
        """Analyze supplied text into unsaved posting named outputs."""
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt") as source:
            source.write(content)
            source.flush()
            posting = self.job_posting_analyzer.analyze(source.name)
        if url is not None:
            posting = posting.model_copy(update={"url": url})
        return {
            PRODUCER_OUTPUT_PRIMARY_FILES["job-postings"]: posting.model_dump(
                mode="json"
            )
        }

    def get_job_posting(self, identifier: str):
        """Retrieve a job posting by identifier."""
        return self.repository.get_job_posting(identifier)

    def get_job_postings(
        self, location: str | None = None, all: bool = False, query: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieve saved job postings.

        Args:
            location: Filter by location. None (default) returns active/unfiled only.
            all: If True and location is None, return all records across all locations.
            query: Optional keyword to filter by company, title, or experience level.

        Returns:
            list of job posting metadata dictionaries
        """
        records = self.repository.get_job_posting_records(location=location, all=all)
        results = [record.model_dump(mode="json") for record in records]
        if query:
            q = query.lower()
            results = [
                r
                for r in results
                if any(
                    q in (r.get(f) or "").lower()
                    for f in (
                        "company",
                        "title",
                        "experience_level",
                        "url",
                        "created_at",
                    )
                )
            ]
        return results

    def transition_job_posting(
        self, identifier: str, location: str, fields: dict | None = None
    ):
        """File a job posting into a named location, recording the transition."""
        return self._transition_job_posting(identifier, location, fields)

    def _transition_job_posting(
        self,
        identifier: str,
        location: str | None,
        fields: dict | None = None,
        record_fields: dict | None = None,
    ) -> JobPostingRecord:
        """Build and persist the lifecycle update."""
        current = self.repository.get_job_posting_record(identifier)
        if current is None:
            raise ValueError(f"Job posting not found: {identifier}")

        normalized_location = None if location == "." else location
        if normalized_location == current.location:
            raise ValueError(f"Job posting already in {location}")

        now = datetime.now()
        entry = {
            "date": now.isoformat(),
            "location": normalized_location if normalized_location is not None else ".",
            **(fields or {}),
        }
        replacement = JobPostingRecord(
            **{
                **current.model_dump(),
                "location": normalized_location,
                "transitions": current.transitions + [entry],
                "updated_at": now,
                **(record_fields or {}),
            }
        )
        record = self.repository.update_job_posting_record(replacement)
        return record

    def archive_job_posting(self, identifier: str):
        """Mark a job posting as archived."""
        return self._transition_job_posting(
            identifier, "archived", record_fields={"is_archived": True}
        )

    def unarchive_job_posting(self, identifier: str):
        """Return a job posting to the root (active/unfiled)."""
        return self._transition_job_posting(
            identifier, ".", record_fields={"is_archived": False}
        )

    def mark_applied(
        self, identifier: str, cv_identifier: str, applied_at: Optional[datetime] = None
    ):
        """Record that a job posting was applied to with a given CV."""
        applied_at_dt = applied_at or datetime.now()
        denorm = {
            "applied_with": cv_identifier,
            "applied_at": applied_at_dt.isoformat(),
        }
        return self._transition_job_posting(
            identifier, "applied", fields=denorm, record_fields=denorm
        )

    def analyze_cv(self, content: str) -> dict[str, Any]:
        """Analyze CV text into named outputs, without saving anything."""
        with tempfile.NamedTemporaryFile("w", suffix=".txt") as source:
            source.write(content)
            source.flush()
            cv = self.cv_analyzer.analyze(source.name)
        return {PRODUCER_OUTPUT_PRIMARY_FILES["cvs"]: cv.model_dump(mode="json")}

    def get_cv(self, identifier: str):
        """Retrieve a CV by identifier."""
        return self.repository.get_cv(identifier)

    def get_cvs(self, query: str | None = None) -> list[dict[str, Any]]:
        """
        Retrieve all saved CVs.

        Returns:
            list of CV metadata dictionaries
        """
        records = self.repository.get_cv_records()
        results = [record.model_dump(mode="json") for record in records]
        if query:
            q = query.lower()
            results = [
                r
                for r in results
                if any(q in (r.get(f) or "").lower() for f in ("name", "identifier"))
            ]
        return results

    def remove(self, entity_uri: str) -> str:
        """Remove an entity and its documents, returning its canonical URI."""
        if self._select_records(entity_uri) is not None:
            raise ValueError(
                f"Cannot remove collection, location or view: {entity_uri}"
            )
        record = self._entity_record(entity_uri)
        entity_type = entity_type_of(record)
        entity_type.remove(self.repository, *entity_type.key(record))
        return self._record_uri(record)

    def rename(self, entity_uri: str, new_identifier: str) -> str:
        """Rename an entity, preserving its documents and relationships."""
        if self._select_records(entity_uri) is not None:
            raise ValueError(
                f"Cannot rename collection, location or view: {entity_uri}"
            )
        validate_identifier(new_identifier)
        record = self._entity_record(entity_uri)
        entity_type = entity_type_of(record)
        renamed = entity_type.rename(
            self.repository, *entity_type.key(record), new_identifier
        )
        return self._record_uri(renamed)

    def export_markdown(self, collection_name: Optional[str] = None) -> int:
        """
        Re-export all markdown files from stored domain objects.

        This overwrites any existing markdown files, including manual edits.
        """
        return self.markdown_exporter.export(collection_name)

    def add_document(self, document_uri: str, content: bytes) -> str:
        """Create exactly the document at document_uri from raw bytes. Returns its URI."""
        document = parse_document_uri(document_uri)
        if document is None:
            raise ValueError(f"{document_uri} is not a document address")
        entity_uri, filename = document
        validate_filename(filename)

        record = resolve_record(self.repository, entity_uri)
        try:
            self.repository.add_document(record, filename, content)
        except DocumentExistsError:
            raise ValueError(f"Document already exists: {document_uri}") from None
        return document_uri

    def optimize(self, cv_uri: str, job_posting_uri: str) -> dict[str, Any]:
        """Optimize a base CV for a posting into named outputs, without saving anything."""
        cv_record = self._require_record(cv_uri, CurriculumVitaeRecord, "base CV")
        posting_record = self._require_record(
            job_posting_uri, JobPostingRecord, "job posting"
        )
        output = self.cv_optimizer.optimize(
            self.repository.load_object(cv_record, CurriculumVitae),
            self.repository.load_object(posting_record, JobPosting),
        )
        return {
            "base_cv_uri": cv_uri,
            PRODUCER_OUTPUT_PRIMARY_FILES["cvs"]: output.cv.model_dump(mode="json"),
            **{
                filename: artifact.model_dump(mode="json")
                for filename, artifact in output.artifacts.items()
            },
        }

    def get_optimized_cvs(self) -> list[dict[str, Any]]:
        """
        Retrieve saved cv optimizations, excluding those whose parent job posting is archived.

        Returns:
            list of optimization metadata dictionaries
        """
        opts = self.repository.get_optimized_cv_records()
        active_job_ids = {
            record.identifier for record in self.repository.get_job_posting_records()
        }
        return [
            record.model_dump(mode="json")
            for record in opts
            if record.job_posting_identifier in active_job_ids
        ]

    def get_cv_optimization(
        self, job_posting_identifier: str, identifier: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Retrieve a specific CV optimization (plan and cv) for viewing.

        Args:
            job_posting_identifier: Identifier of the job posting
            identifier: Identifier of the optimization

        Returns:
            tuple of (plan_data, cv_data)
        """
        record = self.repository.get_optimized_cv_record(
            job_posting_identifier, identifier
        )
        plan = read_transformation_plan(self.repository, record) if record else None
        cv = self.repository.get_optimized_cv(job_posting_identifier, identifier)

        return (
            plan.model_dump() if plan else {},
            cv.model_dump() if cv else {},
        )

    def get_cv_data_filepaths(self) -> list[dict[str, Any]]:
        active_job_ids = {
            record.identifier for record in self.repository.get_job_posting_records()
        }
        results = []
        for record in self.repository.get_cv_records():
            results.append(
                {
                    "identifier": record.identifier,
                    "filepath": str(self.repository.file_for(record, CurriculumVitae)),
                }
            )
        for record in self.repository.get_optimized_cv_records():
            if record.job_posting_identifier in active_job_ids:
                results.append(
                    {
                        "identifier": record.identifier,
                        "job_posting_identifier": record.job_posting_identifier,
                        "filepath": str(
                            self.repository.file_for(record, CurriculumVitae)
                        ),
                    }
                )
        return results

    def get_cv_template_names(self) -> list[str]:
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent
        templates_dir = project_root / "templates"
        return [str(p.name) for p in templates_dir.glob("*cv*.tex")]

    def to_markdown(self, domain_object) -> str:
        return self.markdown_converter.convert(domain_object) or ""

    def get_display_markdown(self, uri: str, obj) -> str:
        base_uri = uri.rsplit("/", 1)[0]
        record = resolve_record(self.repository, base_uri)
        return insert_json_as_frontmatter(
            record.model_dump(mode="json"), self.to_markdown(obj)
        )

    def get_job_posting_record(self, identifier: str):
        return self.repository.get_job_posting_record(identifier)

    def get_cv_record(self, identifier: str):
        return self.repository.get_cv_record(identifier)

    def get_optimized_cv_record(self, job_posting_identifier: str, identifier: str):
        return self.repository.get_optimized_cv_record(
            job_posting_identifier, identifier
        )

    def get_optimized_cv(self, job_posting_identifier: str, identifier: str):
        """Retrieve an optimized CV domain object by job posting and CV identifier."""
        return self.repository.get_optimized_cv(job_posting_identifier, identifier)

    def generate_pdf_file(
        self, data: dict[str, Any], template_name: str, output_path: str
    ) -> str:
        tex = render_tex(data, template_name)
        return tex_to_pdf(tex, output_path)
