import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TypeVar

from pydantic import BaseModel

from models import (
    JobPosting,
    JobPostingRecord,
    CurriculumVitae,
    CurriculumVitaeRecord,
    CoverLetter,
    CoverLetterRecord,
    DOMAIN_OBJECT_REGISTRY,
    OptimizedCvRecord,
)

T = TypeVar("T", bound=BaseModel)

Record = (
    JobPostingRecord | CurriculumVitaeRecord | OptimizedCvRecord | CoverLetterRecord
)


class DocumentExistsError(ValueError):
    """Raised when adding a document that already exists."""


JOB_POSTINGS_DIR = "job-postings"
CVS_DIR = "cvs"
COVER_LETTERS_DIR = "cover-letters"


def _to_kebab_case(name: str) -> str:
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1-\2", s1).lower()


def _job_posting_canonical_path(identifier: str, location: str | None = None) -> str:
    if location:
        return f"{JOB_POSTINGS_DIR}/{location}/{identifier}"
    return f"{JOB_POSTINGS_DIR}/{identifier}"


def _cv_canonical_path(identifier: str) -> str:
    return f"{CVS_DIR}/{identifier}"


def _cover_letter_canonical_path(identifier: str) -> str:
    return f"{COVER_LETTERS_DIR}/{identifier}"


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
        self.optimized_cvs_collection = self.collections_dir / "optimized-cvs.json"
        self.cover_letters_collection = self.collections_dir / "cover-letters.json"

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
        self, record: JobPostingRecord, job_posting: JobPosting
    ) -> JobPostingRecord:
        """
        Add a job posting and update collection metadata.

        Args:
            record: JobPostingRecord
            job_posting: JobPosting

        Returns:
            The persisted JobPostingRecord
        """
        collection = self._load_collection(self.job_postings_collection)

        existing = next(
            (item for item in collection if item["identifier"] == record.identifier),
            None,
        )

        if existing is not None:
            raise ValueError(f"Job posting already exists: {record.identifier}")

        record = record.model_copy(
            update={
                "path": _job_posting_canonical_path(record.identifier, record.location)
            }
        )
        absolute_path = self.directory_for(record) / "job-posting.json"
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        with open(absolute_path, "w") as f:
            json.dump(job_posting.model_dump(mode="json"), f, indent=2)

        collection.append(record.model_dump(mode="json"))
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

    def get_job_posting_records(
        self, location: str | None = None, all: bool = False
    ) -> list[JobPostingRecord]:
        """
        List job postings in the collection.

        Args:
            location: Filter by location. None (default) returns active/unfiled records only.
            all: If True and location is None, return all records across all locations.

        Returns:
            List of job posting records
        """
        collection = self._load_collection(self.job_postings_collection)
        if all and location is None:
            return [JobPostingRecord(**item) for item in collection]
        return [
            JobPostingRecord(**item)
            for item in collection
            if item.get("location") == location
        ]

    def transition_job_posting(
        self,
        identifier: str,
        location: str | None,
        fields: dict[str, Any] | None = None,
        record_fields: dict[str, Any] | None = None,
    ) -> JobPostingRecord:
        """
        Move a job posting to a named location subdirectory, recording the transition.
        """
        collection = self._load_collection(self.job_postings_collection)
        record_data = next(
            (item for item in collection if item["identifier"] == identifier), None
        )
        if record_data is None:
            raise ValueError(f"Job posting not found: {identifier}")

        normalized_location = None if location == "." else location
        target_path = _job_posting_canonical_path(identifier, normalized_location)

        if target_path == record_data.get("path"):
            raise ValueError(f"Job posting already in {location}")

        now = datetime.now()
        entry = {
            "date": now.isoformat(),
            "location": normalized_location if normalized_location is not None else ".",
            **(fields or {}),
        }

        record_data["location"] = normalized_location
        record_data["transitions"] = record_data.get("transitions", []) + [entry]
        record_data["updated_at"] = now.isoformat()
        if record_fields:
            record_data.update(record_fields)

        new_abs = self._resolve_path(target_path)
        new_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(self._resolve_path(record_data["path"])), str(new_abs))
        record_data["path"] = target_path
        self._update_optimized_cv_paths(identifier, target_path)

        self._save_collection(self.job_postings_collection, collection)
        result = JobPostingRecord(**record_data)
        return result

    def _update_optimized_cv_paths(
        self,
        job_posting_identifier: str,
        new_parent_path: str,
        new_job_posting_identifier: str | None = None,
    ) -> None:
        """Keep nested OptimizedCvRecord.path (and job_posting_identifier, if renamed) in sync with their parent."""
        collection = self._load_collection(self.optimized_cvs_collection)
        for item in collection:
            if item.get("job_posting_identifier") != job_posting_identifier:
                continue
            if new_job_posting_identifier is not None:
                item["job_posting_identifier"] = new_job_posting_identifier
            item["path"] = f"{new_parent_path}/{CVS_DIR}/{item['identifier']}"
        self._save_collection(self.optimized_cvs_collection, collection)

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
        removed = next(
            (item for item in collection if item["identifier"] == identifier), None
        )

        if removed is None:
            return False

        collection = [item for item in collection if item["identifier"] != identifier]
        self._save_collection(self.job_postings_collection, collection)

        opt_collection = self._load_collection(self.optimized_cvs_collection)
        opt_collection = [
            item
            for item in opt_collection
            if item.get("job_posting_identifier") != identifier
        ]
        self._save_collection(self.optimized_cvs_collection, opt_collection)

        job_posting_dir = self._resolve_path(removed["path"])
        if job_posting_dir.exists():
            shutil.rmtree(job_posting_dir)

        return True

    def add_cv(
        self, record: CurriculumVitaeRecord, cv: CurriculumVitae
    ) -> CurriculumVitaeRecord:
        """
        Add a CV and update collection metadata.

        Args:
            record: CurriculumVitaeRecord
            cv: CurriculumVitae

        Returns:
            The persisted CurriculumVitaeRecord
        """
        collection = self._load_collection(self.cvs_collection)

        existing = next(
            (item for item in collection if item["identifier"] == record.identifier),
            None,
        )

        if existing is not None:
            raise ValueError(f"CV already exists: {record.identifier}")

        record = record.model_copy(
            update={"path": _cv_canonical_path(record.identifier)}
        )
        absolute_path = self.directory_for(record) / "curriculum-vitae.json"
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        with open(absolute_path, "w") as f:
            json.dump(cv.model_dump(mode="json"), f, indent=2)

        collection.append(record.model_dump(mode="json"))
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

    def get_cv_records(self) -> list[CurriculumVitaeRecord]:
        """
        List base CVs in the collection.

        Returns:
            List of base CV records
        """
        collection = self._load_collection(self.cvs_collection)
        return [
            CurriculumVitaeRecord(**item)
            for item in collection
            if item.get("job_posting_identifier") is None
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
        removed = next(
            (item for item in collection if item["identifier"] == identifier), None
        )

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

        self._update_optimized_cv_paths(identifier, new_path, new_identifier)

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

    def add_cover_letter(
        self, record: CoverLetterRecord, cover_letter: CoverLetter
    ) -> CoverLetterRecord:
        """
        Add a cover letter and update collection metadata.

        Args:
            record: CoverLetterRecord
            cover_letter: CoverLetter

        Returns:
            The persisted CoverLetterRecord
        """
        collection = self._load_collection(self.cover_letters_collection)

        existing = next(
            (item for item in collection if item["identifier"] == record.identifier),
            None,
        )

        if existing is not None:
            raise ValueError(f"Cover letter already exists: {record.identifier}")

        record = record.model_copy(
            update={"path": _cover_letter_canonical_path(record.identifier)}
        )
        absolute_path = self.directory_for(record) / "cover-letter.json"
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        with open(absolute_path, "w") as f:
            json.dump(cover_letter.model_dump(mode="json"), f, indent=2)

        collection.append(record.model_dump(mode="json"))
        self._save_collection(self.cover_letters_collection, collection)

        return record

    def get_cover_letter(self, identifier: str) -> Optional[CoverLetter]:
        """
        Load a cover letter from the filesystem.

        Args:
            identifier: Unique identifier for the cover letter

        Returns:
            CoverLetter or None if not found
        """
        collection = self._load_collection(self.cover_letters_collection)
        metadata = next(
            (item for item in collection if item["identifier"] == identifier), None
        )

        if not metadata:
            return None

        absolute_path = self._resolve_path(metadata["path"]) / "cover-letter.json"
        with open(absolute_path, "r") as f:
            data = json.load(f)

        return CoverLetter(**data)

    def get_cover_letter_record(self, identifier: str) -> Optional[CoverLetterRecord]:
        """
        Load a cover letter record from the collection index.

        Args:
            identifier: Unique identifier for the cover letter

        Returns:
            CoverLetterRecord or None if not found
        """
        collection = self._load_collection(self.cover_letters_collection)
        data = next(
            (item for item in collection if item["identifier"] == identifier), None
        )

        if not data:
            return None

        return CoverLetterRecord(**data)

    def get_cover_letter_records(self) -> list[CoverLetterRecord]:
        """
        List cover letters in the collection.

        Returns:
            List of cover letter records
        """
        return [
            CoverLetterRecord(**item)
            for item in self._load_collection(self.cover_letters_collection)
        ]

    def remove_cover_letter(self, identifier: str) -> bool:
        """
        Remove a cover letter from the collection and delete its data directory.

        Args:
            identifier: Unique identifier for the cover letter

        Returns:
            True if removed, False if not found
        """
        collection = self._load_collection(self.cover_letters_collection)
        removed = next(
            (item for item in collection if item["identifier"] == identifier), None
        )

        if removed is None:
            return False

        collection = [item for item in collection if item["identifier"] != identifier]
        self._save_collection(self.cover_letters_collection, collection)

        letter_dir = self._resolve_path(removed["path"])
        if letter_dir.exists():
            shutil.rmtree(letter_dir)

        return True

    def rename_cover_letter(
        self, identifier: str, new_identifier: str
    ) -> CoverLetterRecord:
        """
        Rename a cover letter, updating its directory and collection entry.

        Args:
            identifier: Current identifier
            new_identifier: New identifier

        Returns:
            Updated CoverLetterRecord

        Raises:
            ValueError: If not found or new identifier already exists
        """
        old_record = self.get_cover_letter_record(identifier)
        if old_record is None:
            raise ValueError(f"Cover letter not found: {identifier}")
        if self.get_cover_letter_record(new_identifier) is not None:
            raise ValueError(f"Cover letter already exists: {new_identifier}")

        new_path = str(Path(old_record.path).parent / new_identifier)
        old_dir = self._resolve_path(old_record.path)
        new_dir = self._resolve_path(new_path)
        new_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_dir), str(new_dir))

        collection = self._load_collection(self.cover_letters_collection)
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
        self._save_collection(self.cover_letters_collection, collection)
        assert new_record_data is not None
        return CoverLetterRecord(**new_record_data)

    def _optimized_cv_path(self, job_posting_identifier: str, identifier: str) -> str:
        """Placement of an optimized CV under its parent job posting's stored path."""
        parent = self.get_job_posting_record(job_posting_identifier)
        parent_path = (
            parent.path if parent else f"job-postings/{job_posting_identifier}"
        )
        return f"{parent_path}/cvs/{identifier}"

    # -------------------------------------------------------------------------
    # Record-addressed storage locations
    # -------------------------------------------------------------------------

    def directory_for(self, record: Record) -> Path:
        """Absolute directory holding a record's objects and documents."""
        return self._resolve_path(record.path)

    def file_for(self, record: Record, model_class: type[BaseModel]) -> Path:
        """Absolute path of a record's stored object of the given class."""
        return self.directory_for(record) / (
            _to_kebab_case(model_class.__name__) + ".json"
        )

    # -------------------------------------------------------------------------
    # Generic object storage (record-addressed, self-describing JSON)
    # -------------------------------------------------------------------------

    def save_object(self, record: Record, obj: BaseModel) -> None:
        path = self.file_for(record, type(obj))
        path.parent.mkdir(parents=True, exist_ok=True)
        data = obj.model_dump(mode="json")
        data["_type"] = type(obj).__name__
        path.write_text(json.dumps(data, indent=2))

    def load_object(self, record: Record, model_class: type[T]) -> Optional[T]:
        path = self.file_for(record, model_class)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        data.pop("_type", None)
        return model_class(**data)

    def load_all_objects(self, record: Record) -> dict[str, BaseModel]:
        directory = self.directory_for(record)
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
    # Document storage (record-addressed, raw text)
    # -------------------------------------------------------------------------

    def add_or_replace_document(
        self, record: Record, filename: str, content: str
    ) -> None:
        directory = self.directory_for(record)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename

        path.write_text(content)

    def add_document(self, record: Record, filename: str, content: str) -> None:
        if self.document_exists(record, filename):
            raise DocumentExistsError(
                f"Document already exists: {record.path}/{filename}"
            )
        self.add_or_replace_document(record, filename, content)

    def load_document(self, record: Record, filename: str) -> str:
        return (self.directory_for(record) / filename).read_text()

    def document_exists(self, record: Record, filename: str) -> bool:
        return (self.directory_for(record) / filename).exists()

    # -------------------------------------------------------------------------
    # Optimized CVs collection
    # -------------------------------------------------------------------------

    def add_optimized_cv(
        self,
        parent: JobPostingRecord,
        record: OptimizedCvRecord,
        cv: CurriculumVitae,
    ) -> OptimizedCvRecord:
        """
        Add an optimized CV and update collection metadata.

        Args:
            parent: The parent JobPostingRecord
            record: OptimizedCvRecord
            cv: The optimized CurriculumVitae

        Returns:
            The persisted OptimizedCvRecord
        """
        if parent is None or parent.path is None:
            raise ValueError("Parent JobPostingRecord required")

        collection = self._load_collection(self.optimized_cvs_collection)

        existing = next(
            (
                item
                for item in collection
                if item["identifier"] == record.identifier
                and item["job_posting_identifier"] == parent.identifier
            ),
            None,
        )

        if existing is not None:
            raise ValueError(
                f"Optimized CV already exists: job-postings/{parent.identifier}/cvs/{record.identifier}"
            )

        record = record.model_copy(
            update={"path": f"{parent.path}/{CVS_DIR}/{record.identifier}"}
        )
        self.save_object(record, cv)
        collection.append(record.model_dump(mode="json"))
        self._save_collection(self.optimized_cvs_collection, collection)
        return record

    def get_optimized_cv_record(
        self, job_posting_identifier: str, identifier: str
    ) -> Optional[OptimizedCvRecord]:
        collection = self._load_collection(self.optimized_cvs_collection)
        data = next(
            (
                item
                for item in collection
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
        record = self.get_optimized_cv_record(job_posting_identifier, identifier)
        if record is None:
            return None
        return self.load_object(record, CurriculumVitae)

    def get_optimized_cv_records(
        self, job_posting_identifier: Optional[str] = None
    ) -> list[OptimizedCvRecord]:
        """
        List optimized CVs in the collection.

        Args:
            job_posting_identifier: If given, only optimized CVs for this job posting.

        Returns:
            List of optimized CV records
        """
        collection = self._load_collection(self.optimized_cvs_collection)
        if job_posting_identifier is not None:
            collection = [
                item
                for item in collection
                if item["job_posting_identifier"] == job_posting_identifier
            ]
        return [OptimizedCvRecord(**item) for item in collection]

    def remove_optimized_cv(self, job_posting_identifier: str, identifier: str) -> bool:
        record = self.get_optimized_cv_record(job_posting_identifier, identifier)
        if record is None:
            return False
        collection = [
            item
            for item in self._load_collection(self.optimized_cvs_collection)
            if not (
                item["identifier"] == identifier
                and item["job_posting_identifier"] == job_posting_identifier
            )
        ]
        self._save_collection(self.optimized_cvs_collection, collection)
        opt_dir = self.directory_for(record)
        if opt_dir.exists():
            shutil.rmtree(opt_dir)
        return True

    def rename_optimized_cv(
        self, job_posting_identifier: str, identifier: str, new_identifier: str
    ) -> OptimizedCvRecord:
        old_record = self.get_optimized_cv_record(job_posting_identifier, identifier)
        if old_record is None:
            raise ValueError(
                f"Optimized CV not found: job-postings/{job_posting_identifier}/cvs/{identifier}"
            )
        if (
            self.get_optimized_cv_record(job_posting_identifier, new_identifier)
            is not None
        ):
            raise ValueError(
                f"Optimized CV already exists: job-postings/{job_posting_identifier}/cvs/{new_identifier}"
            )
        old_dir = self.directory_for(old_record)
        new_path = self._optimized_cv_path(job_posting_identifier, new_identifier)
        shutil.move(str(old_dir), str(self._resolve_path(new_path)))

        collection = self._load_collection(self.optimized_cvs_collection)
        new_record_data = None
        for i, item in enumerate(collection):
            if (
                item["identifier"] == identifier
                and item["job_posting_identifier"] == job_posting_identifier
            ):
                item = dict(item)
                item["identifier"] = new_identifier
                item["path"] = new_path
                item["updated_at"] = datetime.now().isoformat()
                collection[i] = item
                new_record_data = item
                break
        self._save_collection(self.optimized_cvs_collection, collection)
        assert new_record_data is not None
        return OptimizedCvRecord(**new_record_data)
