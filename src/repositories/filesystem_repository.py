import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from models.schema import JobPosting
from models import CurriculumVitae


class FileSystemRepository:
    """
    Repository that stores domain objects on the filesystem with collection metadata.

    Collection metadata is stored in a central location, while domain objects
    can be stored anywhere on the filesystem.
    """

    def __init__(self, collections_dir: Optional[str] = None):
        """
        Initialize the repository.

        Args:
            collections_dir: Directory to store collection metadata files.
                           Defaults to 'collections/' in project root.
        """
        if collections_dir is None:
            collections_dir = os.path.join(os.getcwd(), "collections")

        self.collections_dir = Path(collections_dir)
        self.collections_dir.mkdir(parents=True, exist_ok=True)

        self.job_postings_collection = self.collections_dir / "job_postings.json"
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

    def _generate_default_path(self, collection_name: str, identifier: str) -> str:
        """Generate default file path for a domain object."""
        default_dir = self.collections_dir.parent / collection_name
        default_dir.mkdir(parents=True, exist_ok=True)
        return str(default_dir / identifier / f"{identifier}.json")

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
            file_path = self._generate_default_path("job_postings", identifier)

        file_path = os.path.abspath(file_path)
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w") as f:
            json.dump(job_posting.model_dump(mode='json'), f, indent=2)

        collection = self._load_collection(self.job_postings_collection)

        existing = next((item for item in collection if item["identifier"] == identifier), None)

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
            collection = [item if item["identifier"] != identifier else metadata for item in collection]
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
        metadata = next((item for item in collection if item["identifier"] == identifier), None)

        if not metadata:
            return None

        with open(metadata["filepath"], "r") as f:
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

        file_path = os.path.abspath(file_path)
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w") as f:
            json.dump(cv.model_dump(mode='json'), f, indent=2)

        collection = self._load_collection(self.cvs_collection)

        existing = next((item for item in collection if item["identifier"] == identifier), None)

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
            collection = [item if item["identifier"] != identifier else metadata for item in collection]
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
        metadata = next((item for item in collection if item["identifier"] == identifier), None)

        if not metadata:
            return None

        with open(metadata["filepath"], "r") as f:
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
