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
    DOMAIN_OBJECT_REGISTRY,
    OptimizedCvRecord,
)

T = TypeVar("T", bound=BaseModel)


def _to_kebab_case(name: str) -> str:
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1-\2", s1).lower()


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

    FILE_NAMES = {
        "job-postings": "job-posting.json",
        "cvs": "cv.json",
    }

    def _generate_relative_path(self, collection_name: str, identifier: str) -> str:
        """Generate default relative file path for a domain object."""
        filename = self.FILE_NAMES.get(collection_name, f"{collection_name}.json")
        return f"{collection_name}/{identifier}/{filename}"

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative path against data_dir."""
        return self.data_dir / relative_path

    def upsert_job_posting(
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
        file_path = self._generate_relative_path("job-postings", identifier)

        absolute_path = self._resolve_path(file_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        with open(absolute_path, "w") as f:
            json.dump(job_posting.model_dump(mode="json"), f, indent=2)

        collection = self._load_collection(self.job_postings_collection)

        existing = next(
            (item for item in collection if item["identifier"] == identifier), None
        )

        now = datetime.now()

        record = JobPostingRecord(
            identifier=identifier,
            filepath=file_path,
            url=job_posting.url,
            company=job_posting.company,
            title=job_posting.title,
            experience_level=job_posting.experience_level,
            created_at=datetime.fromisoformat(existing["created_at"])
            if existing
            else now,
            updated_at=now,
        )

        record_dict = record.model_dump(mode="json")

        if existing:
            collection = [
                item if item["identifier"] != identifier else record_dict
                for item in collection
            ]
        else:
            collection.append(record_dict)

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

        absolute_path = self._resolve_path(metadata["filepath"])
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
        self._save_collection(self.job_postings_collection, collection)
        return JobPostingRecord(**record_data)

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
        self._save_collection(self.job_postings_collection, collection)
        return JobPostingRecord(**record_data)

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
        original_length = len(collection)

        collection = [item for item in collection if item["identifier"] != identifier]

        if len(collection) == original_length:
            return False

        self._save_collection(self.job_postings_collection, collection)

        opt_collection = self._load_collection(self.optimized_cvs_collection)
        opt_collection = [
            item for item in opt_collection
            if item.get("job_posting_identifier") != identifier
        ]
        self._save_collection(self.optimized_cvs_collection, opt_collection)

        job_posting_dir = self.data_dir / "job-postings" / identifier
        if job_posting_dir.exists():
            shutil.rmtree(job_posting_dir)

        return True

    def upsert_cv(self, cv: CurriculumVitae, identifier: str) -> CurriculumVitaeRecord:
        """
        Add a CV and update collection metadata.

        Args:
            cv: CurriculumVitae
            identifier: Unique identifier for this CV

        Returns:
            The persisted CurriculumVitaeRecord
        """
        file_path = self._generate_relative_path("cvs", identifier)

        absolute_path = self._resolve_path(file_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        with open(absolute_path, "w") as f:
            json.dump(cv.model_dump(mode="json"), f, indent=2)

        collection = self._load_collection(self.cvs_collection)

        existing = next(
            (item for item in collection if item["identifier"] == identifier), None
        )

        now = datetime.now()

        record = CurriculumVitaeRecord(
            identifier=identifier,
            filepath=file_path,
            name=cv.name,
            profession=cv.profession,
            created_at=datetime.fromisoformat(existing["created_at"])
            if existing
            else now,
            updated_at=now,
        )

        record_dict = record.model_dump(mode="json")

        if existing:
            collection = [
                item if item["identifier"] != identifier else record_dict
                for item in collection
            ]
        else:
            collection.append(record_dict)

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

        absolute_path = self._resolve_path(metadata["filepath"])
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
        original_length = len(collection)

        collection = [item for item in collection if item["identifier"] != identifier]

        if len(collection) == original_length:
            return False

        self._save_collection(self.cvs_collection, collection)

        cv_dir = self.data_dir / "cvs" / identifier
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
        if self.get_job_posting_record(identifier) is None:
            raise ValueError(f"Job posting not found: {identifier}")
        if self.get_job_posting_record(new_identifier) is not None:
            raise ValueError(f"Job posting already exists: {new_identifier}")

        old_dir = self.data_dir / "job-postings" / identifier
        new_dir = self.data_dir / "job-postings" / new_identifier
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
                item["filepath"] = self._generate_relative_path(
                    "job-postings", new_identifier
                )
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
        if self.get_cv_record(identifier) is None:
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

        old_dir = self.data_dir / "cvs" / identifier
        new_dir = self.data_dir / "cvs" / new_identifier
        shutil.move(str(old_dir), str(new_dir))

        collection = self._load_collection(self.cvs_collection)
        new_record_data = None
        for i, item in enumerate(collection):
            if item["identifier"] == identifier:
                item = dict(item)
                item["identifier"] = new_identifier
                item["filepath"] = self._generate_relative_path("cvs", new_identifier)
                item["updated_at"] = datetime.now().isoformat()
                collection[i] = item
                new_record_data = item
                break
        self._save_collection(self.cvs_collection, collection)
        assert new_record_data is not None
        return CurriculumVitaeRecord(**new_record_data)

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
        path = self._resolve_path(uri)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def load_document(self, uri: str) -> str:
        return self._resolve_path(uri).read_text()

    def document_exists(self, uri: str) -> bool:
        return self._resolve_path(uri).exists()

    # -------------------------------------------------------------------------
    # Optimized CVs collection
    # -------------------------------------------------------------------------

    def upsert_optimized_cv(
        self,
        job_posting_identifier: str,
        identifier: str,
        base_cv_identifier: str,
        cv: CurriculumVitae,
    ) -> OptimizedCvRecord:
        opt_dir = self._cv_optimization_dir(job_posting_identifier, identifier)
        opt_dir.mkdir(parents=True, exist_ok=True)
        cv_path = opt_dir / "cv.json"
        cv_path.write_text(json.dumps(cv.model_dump(mode="json"), indent=2))

        job_posting_record = self.get_job_posting_record(job_posting_identifier)
        job_title = job_posting_record.title if job_posting_record else None
        company = job_posting_record.company if job_posting_record else None

        collection = self._load_collection(self.optimized_cvs_collection)
        existing = next(
            (
                item for item in collection
                if item["identifier"] == identifier
                and item["job_posting_identifier"] == job_posting_identifier
            ),
            None,
        )
        now = datetime.now()
        record = OptimizedCvRecord(
            identifier=identifier,
            job_posting_identifier=job_posting_identifier,
            base_cv_identifier=base_cv_identifier,
            name=cv.name,
            profession=cv.profession,
            job_title=job_title,
            company=company,
            created_at=datetime.fromisoformat(existing["created_at"]) if existing else now,
            updated_at=now,
        )
        record_dict = record.model_dump(mode="json")
        if existing:
            collection = [
                record_dict if (
                    item["identifier"] == identifier
                    and item["job_posting_identifier"] == job_posting_identifier
                ) else item
                for item in collection
            ]
        else:
            collection.append(record_dict)
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
        cv_path = self._cv_optimization_dir(job_posting_identifier, identifier) / "cv.json"
        if not cv_path.exists():
            return None
        data = json.loads(cv_path.read_text())
        return CurriculumVitae(**data)

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
