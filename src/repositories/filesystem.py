import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TypeVar

import yaml
from pydantic import BaseModel

from models import (
    JobPosting,
    JobPostingRecord,
    CurriculumVitae,
    CurriculumVitaeRecord,
    DOMAIN_OBJECT_REGISTRY,
    OptimizedCvRecord,
)

T = TypeVar("T", bound=BaseModel)

RECORD_DOCUMENTS: dict[type, set[str]] = {
    JobPostingRecord:      {"job-posting"},
    CurriculumVitaeRecord: {"curriculum-vitae"},
    OptimizedCvRecord:     {"curriculum-vitae", "cv-transformation-plan"},
}


def _render_frontmatter(record: BaseModel) -> str:
    data = record.model_dump(mode="json")
    return f"---\n{yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)}---\n"


def _to_kebab_case(name: str) -> str:
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1-\2", s1).lower()


def parse_uri(uri: str) -> dict[str, str]:
    parts = uri.strip("/").split("/")
    if parts[0] == "job-postings" and len(parts) == 2:
        return {"collection": "job-postings", "identifier": parts[1]}
    if parts[0] == "cvs" and len(parts) == 2:
        return {"collection": "cvs", "identifier": parts[1]}
    if parts[0] == "job-postings" and len(parts) == 4 and parts[2] == "cvs":
        return {"collection": "optimized-cvs", "job_posting_identifier": parts[1], "identifier": parts[3]}
    raise ValueError(f"Unrecognised URI: {uri}")


def _job_posting_canonical_path(record: JobPostingRecord) -> str:
    return f"job-postings/{record.identifier}"


def _cv_canonical_path(record: CurriculumVitaeRecord) -> str:
    return f"cvs/{record.identifier}"


class FileSystemRepository:
    """
    Repository that stores domain objects in the filesystem with metadata records.
    """

    def __init__(self, data_dir: str):
        """
        Initialize the repository.

        Args:
            data_dir: Root directory for all repository data.
        """
        if not data_dir:
            raise ValueError("FilesystemRepository data_dir is required")

        self.data_dir = Path(data_dir).expanduser()
        self.collections_dir = self.data_dir / "collections"
        self.collections_dir.mkdir(parents=True, exist_ok=True)

        self.job_postings_collection = self.collections_dir / "job-postings.json"
        self.cvs_collection = self.collections_dir / "cvs.json"
        self.optimization_plans_collection = (
            self.collections_dir / "optimization-plans.json"
        )
        self.optimized_cvs_collection = self.collections_dir / "optimized-cvs.json"

    def _load_collection(self, collection_file: Path) -> list[dict[str, Any]]:
        """Load collection metadata from JSON file."""
        if not collection_file.exists():
            return []

        with open(collection_file, "r") as f:
            return json.load(f)

    def _save_collection(self, collection_file: Path, collection: list[dict[str, Any]]):
        """Save collection metadata to JSON file."""
        with open(collection_file, "w") as f:
            json.dump(collection, f, indent=2)

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative path against data_dir."""
        return self.data_dir / relative_path

    def add_job_posting(
        self, job_posting: JobPosting, identifier: str
    ) -> JobPostingRecord:
        """
        Add a job posting and update collection metadata.

        Args:
            job_posting: JobPosting
            identifier: Unique identifier for this job posting

        Returns:
            The persisted JobPostingRecord
        """
        collection = self._load_collection(self.job_postings_collection)

        existing = next(
            (item for item in collection if item["identifier"] == identifier), None
        )

        if existing is not None:
            raise ValueError(f"Job posting already exists: {identifier}")

        directory = f"job-postings/{identifier}"
        absolute_path = self._resolve_path(directory) / "job-posting.json"
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        with open(absolute_path, "w") as f:
            json.dump(job_posting.model_dump(mode="json"), f, indent=2)

        now = datetime.now()
        record = JobPostingRecord(
            identifier=identifier,
            path=directory,
            url=job_posting.url,
            company=job_posting.company,
            title=job_posting.title,
            experience_level=job_posting.experience_level,
            created_at=now,
            updated_at=now,
        )

        collection.append(record.model_dump(mode="json", exclude_none=True))
        self._save_collection(self.job_postings_collection, collection)

        return record

    def get_job_posting(self, identifier: str) -> Optional[JobPosting]:
        """
        Load a job posting from the filesystem.

        Args:
            identifier: Unique identifier for the job posting

        Returns:
            JobPosting or None if not found
        """
        collection = self._load_collection(self.job_postings_collection)
        metadata = next(
            (item for item in collection if item["identifier"] == identifier), None
        )

        if not metadata:
            return None

        absolute_path = self._resolve_path(metadata["path"]) / "job-posting.json"
        with open(absolute_path, "r") as f:
            data = json.load(f)

        return JobPosting(**data)

    def get_job_posting_record_by_url(self, url: str) -> Optional[JobPostingRecord]:
        """
        Find a job posting record by URL.

        Returns:
            JobPostingRecord or None if not found
        """
        collection = self._load_collection(self.job_postings_collection)
        data = next((item for item in collection if item.get("url") == url), None)
        if data is None:
            return None
        return JobPostingRecord(**data)

    def get_job_posting_record(self, identifier: str) -> Optional[JobPostingRecord]:
        """
        Load a job posting record from the collection index.

        Args:
            identifier: Unique identifier for the job posting

        Returns:
            JobPostingRecord or None if not found
        """
        collection = self._load_collection(self.job_postings_collection)
        data = next(
            (item for item in collection if item["identifier"] == identifier), None
        )

        if not data:
            return None

        return JobPostingRecord(**data)

    def list_job_postings(self, archived: bool = False) -> list[dict[str, Any]]:
        """
        List job postings in the collection.

        Args:
            archived: If False (default), excludes archived postings.

        Returns:
            List of collection metadata dicts
        """
        collection = self._load_collection(self.job_postings_collection)
        if archived:
            return collection
        return [item for item in collection if not item.get("is_archived", False)]

    def archive_job_posting(self, identifier: str) -> JobPostingRecord:
        """
        Mark a job posting as archived.

        Returns:
            Updated JobPostingRecord
        """
        collection = self._load_collection(self.job_postings_collection)
        record_data = next(
            (item for item in collection if item["identifier"] == identifier), None
        )
        if record_data is None:
            raise ValueError(f"Job posting not found: {identifier}")

        record_data["is_archived"] = True
        record_data["updated_at"] = datetime.now().isoformat()

        record = JobPostingRecord(**record_data)
        target_path = _job_posting_canonical_path(record)
        if target_path != record.path:
            new_abs = self._resolve_path(target_path)
            new_abs.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(self._resolve_path(record.path)), str(new_abs))
            record_data["path"] = target_path

        self._save_collection(self.job_postings_collection, collection)
        result = JobPostingRecord(**record_data)
        self._patch_document_frontmatter(result)
        return result

    def mark_applied(
        self,
        identifier: str,
        cv_identifier: str,
        applied_at: Optional[datetime] = None,
    ) -> JobPostingRecord:
        """
        Record that a job posting was applied to.

        Returns:
            Updated JobPostingRecord
        """
        collection = self._load_collection(self.job_postings_collection)
        record_data = next(
            (item for item in collection if item["identifier"] == identifier), None
        )
        if record_data is None:
            raise ValueError(f"Job posting not found: {identifier}")

        record_data["applied_with"] = cv_identifier
        record_data["applied_at"] = (applied_at or datetime.now()).isoformat()
        record_data["updated_at"] = datetime.now().isoformat()

        record = JobPostingRecord(**record_data)
        target_path = _job_posting_canonical_path(record)
        if target_path != record.path:
            new_abs = self._resolve_path(target_path)
            new_abs.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(self._resolve_path(record.path)), str(new_abs))
            record_data["path"] = target_path

        self._save_collection(self.job_postings_collection, collection)
        result = JobPostingRecord(**record_data)
        self._patch_document_frontmatter(result)
        return result

    def remove_job_posting(self, identifier: str) -> bool:
        """
        Remove a job posting from the collection and delete its data directory.

        Cascades to any nested cvs.

        Args:
            identifier: Unique identifier for the job posting

        Returns:
            True if removed, False if not found
        """
        collection = self._load_collection(self.job_postings_collection)
        removed = next((item for item in collection if item["identifier"] == identifier), None)

        if removed is None:
            return False

        collection = [item for item in collection if item["identifier"] != identifier]
        self._save_collection(self.job_postings_collection, collection)

        opt_collection = self._load_collection(self.optimized_cvs_collection)
        opt_collection = [
            item for item in opt_collection
            if item.get("job_posting_identifier") != identifier
        ]
        self._save_collection(self.optimized_cvs_collection, opt_collection)

        job_posting_dir = self._resolve_path(removed["path"])
        if job_posting_dir.exists():
            shutil.rmtree(job_posting_dir)

        return True

    def add_cv(self, cv: CurriculumVitae, identifier: str) -> CurriculumVitaeRecord:
        """
        Add a CV and update collection metadata.

        Args:
            cv: CurriculumVitae
            identifier: Unique identifier for this CV

        Returns:
            The persisted CurriculumVitaeRecord
        """
        collection = self._load_collection(self.cvs_collection)

        existing = next(
            (item for item in collection if item["identifier"] == identifier), None
        )

        if existing is not None:
            raise ValueError(f"CV already exists: {identifier}")

        directory = f"cvs/{identifier}"
        absolute_path = self._resolve_path(directory) / "curriculum-vitae.json"
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        with open(absolute_path, "w") as f:
            json.dump(cv.model_dump(mode="json"), f, indent=2)

        now = datetime.now()
        record = CurriculumVitaeRecord(
            identifier=identifier,
            path=directory,
            name=cv.name,
            profession=cv.profession,
            created_at=now,
            updated_at=now,
        )

        collection.append(record.model_dump(mode="json", exclude_none=True))
        self._save_collection(self.cvs_collection, collection)

        return record

    def get_cv(self, identifier: str) -> Optional[CurriculumVitae]:
        """
        Load a CV from the filesystem.

        Args:
            identifier: Unique identifier for the CV

        Returns:
            CurriculumVitae or None if not found
        """
        collection = self._load_collection(self.cvs_collection)
        metadata = next(
            (item for item in collection if item["identifier"] == identifier), None
        )

        if not metadata:
            return None

        absolute_path = self._resolve_path(metadata["path"]) / "curriculum-vitae.json"
        with open(absolute_path, "r") as f:
            data = json.load(f)

        return CurriculumVitae(**data)

    def get_cv_record(self, identifier: str) -> Optional[CurriculumVitaeRecord]:
        """
        Load a CV record from the collection index.

        Args:
            identifier: Unique identifier for the CV

        Returns:
            CurriculumVitaeRecord or None if not found
        """
        collection = self._load_collection(self.cvs_collection)
        data = next(
            (item for item in collection if item["identifier"] == identifier), None
        )

        if not data:
            return None

        return CurriculumVitaeRecord(**data)

    def list_cvs(self) -> list[dict[str, Any]]:
        """
        List base CVs in the collection.

        Returns:
            List of collection metadata dicts
        """
        collection = self._load_collection(self.cvs_collection)
        return [
            item for item in collection if item.get("job_posting_identifier") is None
        ]

    def remove_cv(self, identifier: str) -> bool:
        """
        Remove a CV from the collection and delete its data directory.

        Args:
            identifier: Unique identifier for the CV

        Returns:
            True if removed, False if not found
        """
        collection = self._load_collection(self.cvs_collection)
        removed = next((item for item in collection if item["identifier"] == identifier), None)

        if removed is None:
            return False

        collection = [item for item in collection if item["identifier"] != identifier]
        self._save_collection(self.cvs_collection, collection)

        cv_dir = self._resolve_path(removed["path"])
        if cv_dir.exists():
            shutil.rmtree(cv_dir)

        return True

    def rename_job_posting(
        self, identifier: str, new_identifier: str
    ) -> JobPostingRecord:
        """
        Rename a job posting, updating its directory and collection entry.

        Args:
            identifier: Current identifier
            new_identifier: New identifier

        Returns:
            Updated JobPostingRecord

        Raises:
            ValueError: If not found or new identifier already exists
        """
        old_record = self.get_job_posting_record(identifier)
        if old_record is None:
            raise ValueError(f"Job posting not found: {identifier}")
        if self.get_job_posting_record(new_identifier) is not None:
            raise ValueError(f"Job posting already exists: {new_identifier}")

        new_path = str(Path(old_record.path).parent / new_identifier)
        old_dir = self._resolve_path(old_record.path)
        new_dir = self._resolve_path(new_path)
        new_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_dir), str(new_dir))

        opt_collection = self._load_collection(self.optimized_cvs_collection)
        updated_opts = [
            dict(item, job_posting_identifier=new_identifier)
            if item.get("job_posting_identifier") == identifier
            else item
            for item in opt_collection
        ]
        self._save_collection(self.optimized_cvs_collection, updated_opts)

        collection = self._load_collection(self.job_postings_collection)
        new_record_data = None
        for i, item in enumerate(collection):
            if item["identifier"] == identifier:
                item = dict(item)
                item["identifier"] = new_identifier
                item["path"] = new_path
                item["updated_at"] = datetime.now().isoformat()
                collection[i] = item
                new_record_data = item
                break
        self._save_collection(self.job_postings_collection, collection)
        assert new_record_data is not None
        return JobPostingRecord(**new_record_data)

    def rename_cv(self, identifier: str, new_identifier: str) -> CurriculumVitaeRecord:
        """
        Rename a CV, updating its directory, collection entry, and any optimization
        records that reference it via base_cv_identifier.

        Args:
            identifier: Current identifier
            new_identifier: New identifier

        Returns:
            Updated CurriculumVitaeRecord

        Raises:
            ValueError: If not found or new identifier already exists
        """
        old_record = self.get_cv_record(identifier)
        if old_record is None:
            raise ValueError(f"CV not found: {identifier}")
        if self.get_cv_record(new_identifier) is not None:
            raise ValueError(f"CV already exists: {new_identifier}")

        opt_collection = self._load_collection(self.optimized_cvs_collection)
        updated_opts = [
            dict(item, base_cv_identifier=new_identifier)
            if item.get("base_cv_identifier") == identifier
            else item
            for item in opt_collection
        ]
        self._save_collection(self.optimized_cvs_collection, updated_opts)

        new_path = str(Path(old_record.path).parent / new_identifier)
        old_dir = self._resolve_path(old_record.path)
        new_dir = self._resolve_path(new_path)
        new_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_dir), str(new_dir))

        collection = self._load_collection(self.cvs_collection)
        new_record_data = None
        for i, item in enumerate(collection):
            if item["identifier"] == identifier:
                item = dict(item)
                item["identifier"] = new_identifier
                item["path"] = new_path
                item["updated_at"] = datetime.now().isoformat()
                collection[i] = item
                new_record_data = item
                break
        self._save_collection(self.cvs_collection, collection)
        assert new_record_data is not None
        return CurriculumVitaeRecord(**new_record_data)

    def resolve_record(
        self, uri: str
    ) -> JobPostingRecord | CurriculumVitaeRecord | OptimizedCvRecord:
        """Return the governing record for a URI. Raises ValueError if not found."""
        parsed = parse_uri(uri)
        collection = parsed["collection"]

        if collection == "job-postings":
            record = self.get_job_posting_record(parsed["identifier"])
            if record is None:
                raise ValueError(f"Not found: {uri}")
            return record

        if collection == "cvs":
            record = self.get_cv_record(parsed["identifier"])
            if record is None:
                raise ValueError(f"Not found: {uri}")
            return record

        record = self.get_optimized_cv_record(
            parsed["job_posting_identifier"], parsed["identifier"]
        )
        if record is None:
            raise ValueError(f"Not found: {uri}")
        return record

    def canonical_path(self, uri: str) -> str:
        """Return the canonical filesystem path for a URI based on current business rules."""
        parsed = parse_uri(uri)
        collection = parsed["collection"]

        if collection == "job-postings":
            record = self.get_job_posting_record(parsed["identifier"])
            if record is None:
                raise ValueError(f"Not found: {uri}")
            return _job_posting_canonical_path(record)

        if collection == "cvs":
            record = self.get_cv_record(parsed["identifier"])
            if record is None:
                raise ValueError(f"Not found: {uri}")
            return _cv_canonical_path(record)

        parent_path = self.canonical_path(f"job-postings/{parsed['job_posting_identifier']}")
        return f"{parent_path}/cvs/{parsed['identifier']}"

    def _cv_optimization_dir(
        self, job_posting_identifier: str, identifier: str
    ) -> Path:
        return (
            self.data_dir / "job-postings" / job_posting_identifier / "cvs" / identifier
        )

    # -------------------------------------------------------------------------
    # Generic object storage (URI-addressed, self-describing JSON)
    # -------------------------------------------------------------------------

    def save_object(self, base_uri: str, obj: BaseModel) -> None:
        filename = _to_kebab_case(type(obj).__name__) + ".json"
        path = self._resolve_path(base_uri) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        data = obj.model_dump(mode="json")
        data["_type"] = type(obj).__name__
        path.write_text(json.dumps(data, indent=2))

    def load_object(self, base_uri: str, model_class: type[T]) -> Optional[T]:
        filename = _to_kebab_case(model_class.__name__) + ".json"
        path = self._resolve_path(base_uri) / filename
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        data.pop("_type", None)
        return model_class(**data)

    def load_all_objects(self, base_uri: str) -> dict[str, BaseModel]:
        directory = self._resolve_path(base_uri)
        if not directory.exists():
            return {}
        results: dict[str, BaseModel] = {}
        for json_file in directory.glob("*.json"):
            try:
                data = json.loads(json_file.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            type_name = data.get("_type")
            if not type_name or type_name not in DOMAIN_OBJECT_REGISTRY:
                continue
            model_class = DOMAIN_OBJECT_REGISTRY[type_name]
            payload = {k: v for k, v in data.items() if k != "_type"}
            results[json_file.stem] = model_class(**payload)
        return results

    # -------------------------------------------------------------------------
    # Document storage (URI-addressed, raw text)
    # -------------------------------------------------------------------------

    def save_document(self, uri: str, content: str) -> None:
        base_uri, filename = uri.rsplit("/", 1)
        directory = self._resolve_path(self.canonical_path(base_uri))
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename

        if filename.endswith(".md"):
            record = self.resolve_record(base_uri)
            stem = filename[:-3]
            if stem in RECORD_DOCUMENTS.get(type(record), set()):
                content = _render_frontmatter(record) + content

        path.write_text(content)

    def _patch_document_frontmatter(self, record: BaseModel) -> None:
        for stem in RECORD_DOCUMENTS.get(type(record), set()):
            path = self.data_dir / record.path / f"{stem}.md"  # type: ignore[union-attr]
            if not path.exists():
                continue
            content = path.read_text()
            if not content.startswith("---\n"):
                raise ValueError(f"No frontmatter block in {path}")
            end = content.find("\n---\n", 4)
            if end == -1:
                raise ValueError(f"Unclosed frontmatter block in {path}")
            existing = yaml.safe_load(content[4:end]) or {}
            body = content[end + 5:]
            existing.update(record.model_dump(mode="json"))
            new_fm = f"---\n{yaml.dump(existing, default_flow_style=False, allow_unicode=True, sort_keys=False)}---\n"
            path.write_text(new_fm + body)

    def load_document(self, uri: str) -> str:
        return self._resolve_path(uri).read_text()

    def document_exists(self, uri: str) -> bool:
        return self._resolve_path(uri).exists()

    # -------------------------------------------------------------------------
    # Optimized CVs collection
    # -------------------------------------------------------------------------

    def add_optimized_cv(
        self,
        job_posting_identifier: str,
        identifier: str,
        base_cv_identifier: str,
        cv: CurriculumVitae,
    ) -> OptimizedCvRecord:
        """
        Add an optimized CV and update collection metadata.

        Args:
            job_posting_identifier: Identifier of the parent job posting
            identifier: Unique identifier for this optimization
            base_cv_identifier: Identifier of the base CV
            cv: The optimized CurriculumVitae

        Returns:
            The persisted OptimizedCvRecord
        """
        collection = self._load_collection(self.optimized_cvs_collection)

        existing = next(
            (
                item for item in collection
                if item["identifier"] == identifier
                and item["job_posting_identifier"] == job_posting_identifier
            ),
            None,
        )

        if existing is not None:
            raise ValueError(f"Optimized CV already exists: job-postings/{job_posting_identifier}/cvs/{identifier}")

        base_uri = f"job-postings/{job_posting_identifier}/cvs/{identifier}"
        self.save_object(base_uri, cv)

        job_posting_record = self.get_job_posting_record(job_posting_identifier)
        job_title = job_posting_record.title if job_posting_record else None
        company = job_posting_record.company if job_posting_record else None
        path = f"{job_posting_record.path}/cvs/{identifier}" if job_posting_record else f"job-postings/{job_posting_identifier}/cvs/{identifier}"

        now = datetime.now()
        record = OptimizedCvRecord(
            identifier=identifier,
            path=path,
            job_posting_identifier=job_posting_identifier,
            base_cv_identifier=base_cv_identifier,
            name=cv.name,
            profession=cv.profession,
            job_title=job_title,
            company=company,
            created_at=now,
            updated_at=now,
        )
        collection.append(record.model_dump(mode="json"))
        self._save_collection(self.optimized_cvs_collection, collection)
        return record

    def get_optimized_cv_record(
        self, job_posting_identifier: str, identifier: str
    ) -> Optional[OptimizedCvRecord]:
        collection = self._load_collection(self.optimized_cvs_collection)
        data = next(
            (
                item for item in collection
                if item["identifier"] == identifier
                and item["job_posting_identifier"] == job_posting_identifier
            ),
            None,
        )
        if data is None:
            return None
        return OptimizedCvRecord(**data)

    def get_optimized_cv(
        self, job_posting_identifier: str, identifier: str
    ) -> Optional[CurriculumVitae]:
        base_uri = f"job-postings/{job_posting_identifier}/cvs/{identifier}"
        return self.load_object(base_uri, CurriculumVitae)

    def list_optimized_cvs(
        self, job_posting_identifier: Optional[str] = None
    ) -> list[dict[str, Any]]:
        collection = self._load_collection(self.optimized_cvs_collection)
        if job_posting_identifier is not None:
            collection = [
                item for item in collection
                if item["job_posting_identifier"] == job_posting_identifier
            ]
        return collection

    def remove_optimized_cv(
        self, job_posting_identifier: str, identifier: str
    ) -> bool:
        collection = self._load_collection(self.optimized_cvs_collection)
        original_length = len(collection)
        collection = [
            item for item in collection
            if not (
                item["identifier"] == identifier
                and item["job_posting_identifier"] == job_posting_identifier
            )
        ]
        if len(collection) == original_length:
            return False
        self._save_collection(self.optimized_cvs_collection, collection)
        opt_dir = self._cv_optimization_dir(job_posting_identifier, identifier)
        if opt_dir.exists():
            shutil.rmtree(opt_dir)
        return True

    def rename_optimized_cv(
        self, job_posting_identifier: str, identifier: str, new_identifier: str
    ) -> OptimizedCvRecord:
        if self.get_optimized_cv_record(job_posting_identifier, identifier) is None:
            raise ValueError(
                f"Optimized CV not found: job-postings/{job_posting_identifier}/cvs/{identifier}"
            )
        if self.get_optimized_cv_record(job_posting_identifier, new_identifier) is not None:
            raise ValueError(
                f"Optimized CV already exists: job-postings/{job_posting_identifier}/cvs/{new_identifier}"
            )
        old_dir = self._cv_optimization_dir(job_posting_identifier, identifier)
        new_dir = self._cv_optimization_dir(job_posting_identifier, new_identifier)
        shutil.move(str(old_dir), str(new_dir))

        collection = self._load_collection(self.optimized_cvs_collection)
        new_record_data = None
        for i, item in enumerate(collection):
            if (
                item["identifier"] == identifier
                and item["job_posting_identifier"] == job_posting_identifier
            ):
                item = dict(item)
                item["identifier"] = new_identifier
                item["updated_at"] = datetime.now().isoformat()
                collection[i] = item
                new_record_data = item
                break
        self._save_collection(self.optimized_cvs_collection, collection)
        assert new_record_data is not None
        return OptimizedCvRecord(**new_record_data)

    def purge_optimized_cv(
        self, job_posting_identifier: str, identifier: str
    ) -> bool:
        opt_dir = self._cv_optimization_dir(job_posting_identifier, identifier)
        if not opt_dir.exists():
            return False
        shutil.rmtree(opt_dir)
        return True
