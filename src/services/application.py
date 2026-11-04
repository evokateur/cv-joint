from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime
from typing import Any, Callable, Optional

from config.root import get_settings
from models import (
    CurriculumVitae,
    CvTransformationPlan,
    JobPosting,
    JobPostingRecord,
    OptimizedCvRecord,
)
from services.analyzers import JobPostingAnalyzer
from services.analyzers import CvAnalyzer
from services.analyzers import CvOptimizer
from .converters import MarkdownConverter, insert_json_as_frontmatter
from .exporters import MarkdownExporter
from repositories import DocumentExistsError, FileSystemRepository
from services.addressing import (
    parse_document_uri,
    parse_uri,
    resolve_record,
    validate_filename,
    validate_identifier,
)
from renderers.latex import render_tex, tex_to_pdf


def _document_bytes(content: Any) -> bytes:
    """Encode a named output: strings as UTF-8 text, anything else as JSON."""
    if isinstance(content, str):
        return content.encode()
    return json.dumps(content, indent=2).encode()


def _next_identifier(identifier: str, exists: Callable[[str], Any]) -> str:
    stripped = re.sub(r"-\d+$", "", identifier)
    base = stripped if stripped != identifier and exists(stripped) else identifier
    counter = 2
    candidate = f"{base}-{counter}"
    while exists(candidate):
        counter += 1
        candidate = f"{base}-{counter}"
    return candidate


def _slugify(text: str) -> str:
    """Lowercase, drop punctuation, and hyphenate whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")


def _slugify_job(company: str, title: str) -> str:
    if company.lower() == "not specified":
        return _slugify(title)
    return f"{_slugify(company)}-{_slugify(title)}"


class ApplicationService:
    """
    Application service for CV Joint operations.
    """

    def __init__(
        self,
        repository: Optional[FileSystemRepository] = None,
        cv_analyzer: Optional[CvAnalyzer] = None,
    ):
        self.job_posting_analyzer = JobPostingAnalyzer()
        self.cv_analyzer = cv_analyzer or CvAnalyzer()
        self.cv_optimizer = CvOptimizer()
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

    def add(
        self, collection_uri: str, data: dict[str, Any] | str, *, identifier: str
    ) -> str:
        """Create one entity in a collection from a dict or JSON text. Returns the entity URI."""
        if isinstance(data, str):
            data = json.loads(data)
        if not isinstance(data, dict):
            raise ValueError("Entity content must be a JSON object")
        validate_identifier(identifier)
        entity_uri = f"{collection_uri}/{identifier}"
        if self.object_exists(entity_uri):
            raise ValueError(f"Already exists: {entity_uri}")
        parts = collection_uri.strip("/").split("/")
        if parts == ["job-postings"]:
            record = self.add_job_posting(data, identifier)
        elif len(parts) == 3 and parts[0] == "job-postings" and parts[2] == "cvs":
            resolve_record(self.repository, f"job-postings/{parts[1]}")
            record = self.add_optimized_cv(
                parts[1], identifier, None, CurriculumVitae(**data)
            )
        elif parts == ["cvs"]:
            record = self.add_cv(data, identifier)
        else:
            raise ValueError(f"Cannot add to {collection_uri}")
        return self._record_uri(record)

    def load(
        self, destination_uri: str, outputs: dict[str, Any] | str, *, identifier: str
    ) -> str:
        """Create one entity at a destination from named outputs. Returns the entity URI."""
        if isinstance(outputs, str):
            try:
                outputs = json.loads(outputs)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid named outputs: {error}") from None
        self._validate_load(destination_uri, outputs)
        entity_uri = self.add(
            destination_uri, outputs["curriculum-vitae.json"], identifier=identifier
        )
        for filename, content in outputs.items():
            if filename != "curriculum-vitae.json":
                self.add_document(
                    entity_uri, _document_bytes(content), filename=filename
                )
        return entity_uri

    def _validate_load(self, destination_uri: str, outputs: dict[str, Any]) -> None:
        """Reject named outputs that load can't write in full."""
        if destination_uri != "cvs":
            raise ValueError(f"Cannot load into {destination_uri}")
        if "curriculum-vitae.json" not in outputs:
            raise ValueError("Missing curriculum-vitae.json")
        if "base_uri" in outputs:
            raise ValueError("base_uri is not allowed: base CVs have no provenance")
        for filename in outputs:
            validate_filename(filename)

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
        if isinstance(record, JobPostingRecord):
            content = JobPosting(**data)
            fields = ("url", "company", "title", "experience_level")
        else:
            content = CurriculumVitae(**data)
            fields = ("name", "profession")
        summary = {field: getattr(content, field) for field in fields}
        replacement = record.model_copy(
            update={**summary, "updated_at": datetime.now()}
        )
        self.repository.save_object(record, content)
        if isinstance(record, JobPostingRecord):
            self.repository.update_job_posting_record(replacement)
        else:
            self.repository.update_cv_record(replacement)
        return self._record_uri(record)

    def get(self, target: str, *, recursive=False, query=None):
        """Read content or select collection records by logical address."""
        records = self._select_records(target, recursive=recursive, query=query)
        if records is not None:
            return records
        record = self._entity_record(target)
        model = JobPosting if isinstance(record, JobPostingRecord) else CurriculumVitae
        content = self.repository.load_object(record, model)
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
        elif parts == ["cvs"]:
            records = self.repository.get_cv_records()
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
        if isinstance(record, JobPostingRecord):
            uris.append(f"{uri}/cvs")
        return uris

    def _entity_record(self, target: str):
        if target.strip("/").split("/")[0] not in ("job-postings", "cvs"):
            raise ValueError(f"Unrecognised target: {target}")
        return resolve_record(self.repository, target)

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

    def complete_targets(self, incomplete: str) -> list[str]:
        """Complete logical reading targets across every location."""
        candidates = {"job-postings", "cvs", "optimized-cvs"}
        for location in self.list_locations():
            candidates.update((f"job-postings/{location}", f"optimized-cvs/{location}"))
        records = (
            self.repository.get_job_posting_records(all=True)
            + self.repository.get_cv_records()
            + self.repository.get_optimized_cv_records()
        )
        for record in records:
            uri = self._record_uri(record)
            candidates.add(uri)
            candidates.update(
                f"{uri}/{filename}"
                for filename in self.repository.list_documents(record)
            )
            if isinstance(record, JobPostingRecord):
                candidates.add(f"{uri}/cvs")
        return sorted(
            candidate for candidate in candidates if candidate.startswith(incomplete)
        )

    @staticmethod
    def _record_uri(record) -> str:
        if isinstance(record, OptimizedCvRecord):
            return (
                f"job-postings/{record.job_posting_identifier}/cvs/{record.identifier}"
            )
        collection = "job-postings" if isinstance(record, JobPostingRecord) else "cvs"
        return f"{collection}/{record.identifier}"

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
        collection = parsed["collection"]
        if collection == "job-postings":
            return self.repository.get_job_posting(parsed["identifier"]) is not None
        if collection == "cvs":
            return self.repository.get_cv(parsed["identifier"]) is not None
        if collection == "cover-letters":
            return self.repository.get_cover_letter(parsed["identifier"]) is not None
        if collection == "optimized-cvs":
            return (
                self.repository.get_optimized_cv(
                    parsed["job_posting_identifier"], parsed["identifier"]
                )
                is not None
            )
        return False

    def unique_new_identifier(self, uri: str) -> str:
        """A free identifier in uri's namespace: its terminal segment, or a
        -N variant when that collides."""
        prefix, terminal = uri.rsplit("/", 1)

        def exists(identifier: str) -> bool:
            return self.object_exists(f"{prefix}/{identifier}")

        if not exists(terminal):
            return terminal
        return _next_identifier(terminal, exists)

    def generate_default_identifier(
        self, collection: str, data: dict[str, Any]
    ) -> str | None:
        """A collision-free default identifier derived from an object's fields.

        None when the collection has no default identifier defined.
        """
        if collection == "job-postings":
            slug = _slugify_job(data["company"], data["title"])
        elif collection == "cvs":
            slug = _slugify(data["profession"])
        else:
            return None
        return self.unique_new_identifier(f"{collection}/{slug}")

    def _analyze_job_posting_url(self, url: str) -> JobPosting:
        """Fetch a URL and analyze its content as a job posting.

        The fetched content lives in a context-managed temp file for the
        duration of the analysis, then is cleaned up automatically.
        """
        import requests

        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".html") as tmp:
            tmp.write(resp.content)
            tmp.flush()
            return self.job_posting_analyzer.analyze(tmp.name)

    def analyze_job_posting(
        self, url: str, content_file: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Analyze a job posting into a structured JobPosting.

        Args:
            url: Job posting URL — stored as provenance. Content is fetched from
                this URL unless content_file is supplied (e.g. sites that only
                yield content in a browser). Re-analyzing the same URL is allowed.
            content_file: Local file path to analyze in lieu of fetching the URL

        Returns:
            job_posting_data; pass to add_job_posting (with an identifier) to persist.
        """
        if content_file is None:
            job_posting = self._analyze_job_posting_url(url)
        else:
            job_posting = self.job_posting_analyzer.analyze(content_file)

        job_posting = job_posting.model_copy(update={"url": url})
        return job_posting.model_dump()

    def add_job_posting(self, job_posting_data: dict[str, Any], identifier: str):
        """
        Add a job posting to the repository under identifier.

        Args:
            job_posting_data: Job posting data dict (from analyze_job_posting)
            identifier: Identifier to use for this job posting

        Returns:
            JobPostingRecord

        Raises:
            ValueError: if identifier already exists
        """
        from models import JobPosting, JobPostingRecord

        job_posting = JobPosting(**job_posting_data)
        now = datetime.now()
        record = JobPostingRecord(
            identifier=identifier,
            url=job_posting.url,
            company=job_posting.company,
            title=job_posting.title,
            experience_level=job_posting.experience_level,
            created_at=now,
            updated_at=now,
        )
        record = self.repository.add_job_posting(record, job_posting)
        return record

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
        return {"curriculum-vitae.json": cv.model_dump(mode="json")}

    def add_cv(self, cv_data: dict[str, Any], identifier: str):
        """
        Add a CV to the repository under identifier.

        Args:
            cv_data: CV data dict (from analyze_cv)
            identifier: Identifier to use for this CV

        Returns:
            CurriculumVitaeRecord

        Raises:
            ValueError: if identifier already exists
        """
        from models import CurriculumVitae, CurriculumVitaeRecord

        cv = CurriculumVitae(**cv_data)
        now = datetime.now()
        record = CurriculumVitaeRecord(
            identifier=identifier,
            name=cv.name,
            profession=cv.profession,
            created_at=now,
            updated_at=now,
        )
        record = self.repository.add_cv(record, cv)
        return record

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

    def remove_job_posting(self, identifier: str) -> bool:
        """
        Remove a job posting and all nested cv optimizations.

        Args:
            identifier: Identifier of the job posting

        Returns:
            True if removed, False if not found
        """
        return self.repository.remove_job_posting(identifier)

    def remove_cv(self, identifier: str) -> bool:
        """
        Remove a CV.

        Args:
            identifier: Identifier of the CV

        Returns:
            True if removed, False if not found

        """
        return self.repository.remove_cv(identifier)

    def remove_optimized_cv(self, job_posting_identifier: str, identifier: str) -> bool:
        """
        Remove a saved cv optimization.

        Args:
            job_posting_identifier: Identifier of the parent job posting
            identifier: Identifier of the optimization

        Returns:
            True if removed, False if not found
        """
        return self.repository.remove_optimized_cv(job_posting_identifier, identifier)

    def rename_job_posting(self, identifier: str, new_identifier: str):
        """
        Rename a job posting, moving its data and markdown to the new identifier.

        Raises:
            ValueError: If not found or new identifier already exists
        """
        return self.repository.rename_job_posting(identifier, new_identifier)

    def rename_cv(self, identifier: str, new_identifier: str):
        """
        Rename a CV, moving its data and markdown to the new identifier.
        Also repairs any cv optimization records that reference this CV.

        Raises:
            ValueError: If not found or new identifier already exists
        """
        return self.repository.rename_cv(identifier, new_identifier)

    def rename_optimized_cv(
        self, job_posting_identifier: str, identifier: str, new_identifier: str
    ):
        """
        Rename a CV optimization, moving its data and markdown to the new identifier.

        Raises:
            ValueError: If not found or new identifier already exists
        """
        return self.repository.rename_optimized_cv(
            job_posting_identifier, identifier, new_identifier
        )

    def export_markdown(self, collection_name: Optional[str] = None) -> int:
        """
        Re-export all markdown files from stored domain objects.

        This overwrites any existing markdown files, including manual edits.
        """
        return self.markdown_exporter.export(collection_name)

    def add_document(
        self, target_uri: str, content: bytes, *, filename: str | None = None
    ) -> str:
        """Attach raw bytes to an entity as a new document. Returns the document URI."""
        entity_uri = target_uri
        document = parse_document_uri(target_uri)
        if document is not None:
            entity_uri, filename = document
        validate_filename(filename)
        doc_uri = f"{entity_uri}/{filename}"
        if parse_document_uri(doc_uri) is None:
            raise ValueError(f"{doc_uri} is not a document address")

        record = resolve_record(self.repository, entity_uri)
        try:
            self.repository.add_document(record, filename, content)
        except DocumentExistsError:
            raise ValueError(f"Document already exists: {doc_uri}") from None
        return doc_uri

    def optimize_cv(
        self, job_posting_identifier: str, cv_identifier: str
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        """
        Analyze a CV optimization for a job posting.

        Args:
            job_posting_identifier: Identifier of the job posting
            cv_identifier: Identifier of the base CV

        Returns:
            tuple of (plan_data, cv_data, identifiers_dict); pass to add_optimized_cv to persist.
            identifiers_dict contains job_posting_identifier, identifier, base_cv_identifier
        """
        import datetime

        cv = self.repository.get_cv(cv_identifier)
        job_posting = self.repository.get_job_posting(job_posting_identifier)

        if cv is None or job_posting is None:
            raise ValueError(
                f"CV or job posting not found: {cv_identifier}, {job_posting_identifier}"
            )

        identifier = f"{cv_identifier}-{datetime.date.today()}"

        output = self.cv_optimizer.optimize(cv, job_posting)
        plan = output.artifacts.get("transformation-plan")

        identifiers = {
            "job_posting_identifier": job_posting_identifier,
            "identifier": identifier,
            "base_cv_identifier": cv_identifier,
        }

        return (
            plan.model_dump() if plan else {},
            output.cv.model_dump(),
            identifiers,
        )

    def add_optimized_cv(
        self,
        job_posting_identifier: str,
        identifier: str,
        base_cv_identifier: str | None,
        cv: CurriculumVitae,
        plan: CvTransformationPlan | None = None,
    ):
        """
        Add a CV optimization to the repository.

        Args:
            job_posting_identifier: Identifier of the job posting
            identifier: Identifier for this optimization
            base_cv_identifier: Identifier of the base CV, or None if not recorded
            cv: The optimized CV
            plan: The transformation plan, if any

        Returns:
            OptimizedCvRecord
        """
        from models import OptimizedCvRecord

        parent = self.repository.get_job_posting_record(job_posting_identifier)
        now = datetime.now()
        record = OptimizedCvRecord(
            identifier=identifier,
            job_posting_identifier=job_posting_identifier,
            base_cv_identifier=base_cv_identifier,
            name=cv.name,
            profession=cv.profession,
            job_title=parent.title,
            company=parent.company,
            created_at=now,
            updated_at=now,
        )
        record = self.repository.add_optimized_cv(parent, record, cv)

        if plan is not None:
            self.repository.save_object(record, plan)

        return record

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
        plan = (
            self.repository.load_object(record, CvTransformationPlan)
            if record
            else None
        )
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
