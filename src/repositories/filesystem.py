import json
import os
from datetime import datetime
from models import JobPosting, CurriculumVitae
from pathlib import Path
from typing import Any, Optional

from repositories.config.settings import get_config


class FileSystemRepository:
    """
    Repository that stores domain objects on the filesystem with collection metadata.

    Collection metadata is stored in a central location, while domain objects
    can be stored anywhere on the filesystem.
    """

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize the repository.

        Args:
            data_dir: Root directory for all repository data.
                      Defaults to configured value or current working directory.
        """
        if data_dir is None:
            config = get_config()
            data_dir = config.data_dir
            if data_dir == ".":
                data_dir = os.getcwd()

        self.data_dir = Path(data_dir).expanduser()
        self.collections_dir = self.data_dir / "collections"
        self.collections_dir.mkdir(parents=True, exist_ok=True)

        self.job_postings_collection = self.collections_dir / "job-postings.json"
        self.cvs_collection = self.collections_dir / "cvs.json"

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

    def _generate_default_path(self, collection_name: str, identifier: str) -> str:
        """Generate default relative file path for a domain object."""
        filename = self.FILE_NAMES.get(collection_name, f"{collection_name}.json")
        return f"{collection_name}/{identifier}/{filename}"

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative path against data_dir."""
        return self.data_dir / relative_path

    def save_job_posting(
        self, job_posting: JobPosting, identifier: str, file_path: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Save a job posting and update collection metadata.

        Args:
            job_posting: JobPosting domain object
            identifier: Unique identifier for this job posting
            file_path: Optional path to save the file. If None, generates default path.

        Returns:
            Collection metadata dict for this job posting
        """
        if file_path is None:
            file_path = self._generate_default_path("job-postings", identifier)

        absolute_path = self._resolve_path(file_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        with open(absolute_path, "w") as f:
            json.dump(job_posting.model_dump(mode="json"), f, indent=2)

        collection = self._load_collection(self.job_postings_collection)

        existing = next(
            (item for item in collection if item["identifier"] == identifier), None
        )

        now = datetime.now().isoformat()

        metadata = {
            "identifier": identifier,
            "filepath": file_path,
            "url": job_posting.url,
            "company": job_posting.company,
            "title": job_posting.title,
            "experience_level": job_posting.experience_level,
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
        }

        if existing:
            collection = [
                item if item["identifier"] != identifier else metadata
                for item in collection
            ]
        else:
            collection.append(metadata)

        self._save_collection(self.job_postings_collection, collection)

        return metadata

    def get_job_posting(self, identifier: str) -> Optional[JobPosting]:
        """
        Load a job posting from the filesystem.

        Args:
            identifier: Unique identifier for the job posting

        Returns:
            JobPosting domain object or None if not found
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

    def list_job_postings(self) -> list[dict[str, Any]]:
        """
        List all job postings in the collection.

        Returns:
            List of collection metadata dicts
        """
        return self._load_collection(self.job_postings_collection)

    def delete_job_posting(self, identifier: str) -> bool:
        """
        Remove a job posting from the collection.

        Note: Does not delete the actual file, only removes from collection.

        Args:
            identifier: Unique identifier for the job posting

        Returns:
            True if removed, False if not found
        """
        collection = self._load_collection(self.job_postings_collection)
        original_length = len(collection)

        collection = [item for item in collection if item["identifier"] != identifier]

        if len(collection) < original_length:
            self._save_collection(self.job_postings_collection, collection)
            return True

        return False

    def save_cv(
        self, cv: CurriculumVitae, identifier: str, file_path: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Save a CV and update collection metadata.

        Args:
            cv: CurriculumVitae domain object
            identifier: Unique identifier for this CV
            file_path: Optional path to save the file. If None, generates default path.

        Returns:
            Collection metadata dict for this CV
        """
        if file_path is None:
            file_path = self._generate_default_path("cvs", identifier)

        absolute_path = self._resolve_path(file_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        with open(absolute_path, "w") as f:
            json.dump(cv.model_dump(mode="json"), f, indent=2)

        collection = self._load_collection(self.cvs_collection)

        existing = next(
            (item for item in collection if item["identifier"] == identifier), None
        )

        now = datetime.now().isoformat()

        metadata = {
            "identifier": identifier,
            "filepath": file_path,
            "name": cv.name,
            "profession": cv.profession,
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
        }

        if existing:
            collection = [
                item if item["identifier"] != identifier else metadata
                for item in collection
            ]
        else:
            collection.append(metadata)

        self._save_collection(self.cvs_collection, collection)

        return metadata

    def get_cv(self, identifier: str) -> Optional[CurriculumVitae]:
        """
        Load a CV from the filesystem.

        Args:
            identifier: Unique identifier for the CV

        Returns:
            CurriculumVitae domain object or None if not found
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

    def list_cvs(self) -> list[dict[str, Any]]:
        """
        List all CVs in the collection.

        Returns:
            List of collection metadata dicts
        """
        return self._load_collection(self.cvs_collection)

    def delete_cv(self, identifier: str) -> bool:
        """
        Remove a CV from the collection.

        Note: Does not delete the actual file, only removes from collection.

        Args:
            identifier: Unique identifier for the CV

        Returns:
            True if removed, False if not found
        """
        collection = self._load_collection(self.cvs_collection)
        original_length = len(collection)

        collection = [item for item in collection if item["identifier"] != identifier]

        if len(collection) < original_length:
            self._save_collection(self.cvs_collection, collection)
            return True

        return False
