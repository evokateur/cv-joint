import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from converters import to_markdown
from models import (
    JobPosting,
    CurriculumVitae,
    CvOptimizationRecord,
    CvTransformationPlan,
)
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

    def add_job_posting(
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

        md_path = absolute_path.with_suffix(".md")
        if job_posting.company and job_posting.company.lower() != "not specified":
            title = f"{job_posting.title} at {job_posting.company}"
        else:
            title = job_posting.title
        md_path.write_text(to_markdown(job_posting, title=title))

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

        job_posting = JobPosting(**data)

        md_path = absolute_path.with_suffix(".md")
        if not md_path.exists():
            if job_posting.company and job_posting.company.lower() != "not specified":
                title = f"{job_posting.title} at {job_posting.company}"
            else:
                title = job_posting.title
            md_path.write_text(to_markdown(job_posting, title=title))

        return job_posting

    def list_job_postings(self) -> list[dict[str, Any]]:
        """
        List all job postings in the collection.

        Returns:
            List of collection metadata dicts
        """
        return self._load_collection(self.job_postings_collection)

    def remove_job_posting(self, identifier: str) -> bool:
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

    def add_cv(
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

        md_path = absolute_path.with_suffix(".md")
        md_path.write_text(to_markdown(cv, title=cv.name))

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

        cv = CurriculumVitae(**data)

        md_path = absolute_path.with_suffix(".md")
        if not md_path.exists():
            md_path.write_text(to_markdown(cv, title=cv.name))

        return cv

    def list_cvs(self) -> list[dict[str, Any]]:
        """
        List all CVs in the collection.

        Returns:
            List of collection metadata dicts
        """
        return self._load_collection(self.cvs_collection)

    def remove_cv(self, identifier: str) -> bool:
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

    def clear_markdown(
        self,
        collection_name: Optional[str] = None,
        identifier: Optional[str] = None,
    ) -> int:
        """
        Remove generated markdown files from job-postings and cvs directories.

        Only removes markdown files that correspond to stored JSON files
        (e.g., job-posting.md alongside job-posting.json).

        Args:
            collection_name: Optional "job-postings" or "cvs" to limit scope
            identifier: Optional identifier to clear only one item (requires collection_name)

        Returns:
            Number of markdown files deleted
        """
        collections = {
            "job-postings": self.job_postings_collection,
            "cvs": self.cvs_collection,
        }

        if collection_name:
            if collection_name not in collections:
                raise ValueError(f"Unknown collection: {collection_name}")
            collections = {collection_name: collections[collection_name]}

        if identifier:
            found = False
            for collection_file in collections.values():
                collection = self._load_collection(collection_file)
                if any(item["identifier"] == identifier for item in collection):
                    found = True
                    break
            if not found:
                raise ValueError(
                    f"Identifier not found in {collection_name}: {identifier}"
                )

        count = 0

        for collection_file in collections.values():
            collection = self._load_collection(collection_file)
            for item in collection:
                if identifier and item["identifier"] != identifier:
                    continue
                json_path = self._resolve_path(item["filepath"])
                md_path = json_path.with_suffix(".md")
                if md_path.exists():
                    md_path.unlink()
                    count += 1

        return count

    def _cv_optimization_dir(
        self, job_posting_identifier: str, identifier: str
    ) -> Path:
        """Get the directory path for an optimization."""
        return (
            self.data_dir
            / "job-postings"
            / job_posting_identifier
            / "cv-optimizations"
            / identifier
        )

    def add_cv_optimization(
        self,
        job_posting_identifier: str,
        record: CvOptimizationRecord,
    ) -> dict[str, Any]:
        """
        Persist CV optimization record.

        The transformation plan and optimized CV files are assumed to already exist.

        Args:
            job_posting_identifier: Identifier of the parent job posting
            record: The cv optimization record to save

        Returns:
            Metadata dict for the saved optimization
        """
        optimization_dir = self._cv_optimization_dir(
            job_posting_identifier, record.identifier
        )
        optimization_dir.mkdir(parents=True, exist_ok=True)

        optimization_path = optimization_dir / "record.json"
        with open(optimization_path, "w") as f:
            json.dump(record.model_dump(mode="json"), f, indent=2)

        return {
            "identifier": record.identifier,
            "job_posting_identifier": job_posting_identifier,
            "base_cv_identifier": record.base_cv_identifier,
            "created_at": record.created_at.isoformat(),
        }

    def list_cv_optimizations(
        self,
        job_posting_identifier: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        List optimizations, optionally filtered by job posting.

        Only returns directories that have record.json (the save marker).

        Args:
            job_posting_identifier: If provided, list only for this job posting.
                                   If None, list all optimizations across all job postings.

        Returns:
            List of optimization metadata dicts
        """
        results = []

        if job_posting_identifier is not None:
            job_posting_dirs = [self.data_dir / "job-postings" / job_posting_identifier]
        else:
            job_postings_root = self.data_dir / "job-postings"
            if not job_postings_root.exists():
                return []
            job_posting_dirs = [d for d in job_postings_root.iterdir() if d.is_dir()]

        for job_posting_dir in job_posting_dirs:
            cv_optimizations_dir = job_posting_dir / "cv-optimizations"
            if not cv_optimizations_dir.exists():
                continue

            jp_identifier = job_posting_dir.name

            for optimization_dir in cv_optimizations_dir.iterdir():
                if not optimization_dir.is_dir():
                    continue

                record_path = optimization_dir / "record.json"
                if not record_path.exists():
                    continue

                with open(record_path, "r") as f:
                    record_data = json.load(f)

                result = {
                    "identifier": optimization_dir.name,
                    "job_posting_identifier": jp_identifier,
                    "base_cv_identifier": record_data.get("base_cv_identifier"),
                    "created_at": record_data.get("created_at"),
                }

                plan_path = optimization_dir / "transformation-plan.json"
                if plan_path.exists():
                    with open(plan_path, "r") as f:
                        plan_data = json.load(f)
                    result["job_title"] = plan_data.get("job_title")
                    result["company"] = plan_data.get("company")

                results.append(result)

        return results

    def get_cv_optimization_record(
        self,
        job_posting_identifier: str,
        identifier: str,
    ) -> Optional[CvOptimizationRecord]:
        """
        Load optimization metadata from record.json.

        Args:
            job_posting_identifier: Identifier of the parent job posting
            identifier: Identifier of the optimization

        Returns:
            CvOptimizationRecord or None if not found
        """
        record_path = (
            self._cv_optimization_dir(job_posting_identifier, identifier)
            / "record.json"
        )

        if not record_path.exists():
            return None

        with open(record_path, "r") as f:
            data = json.load(f)

        return CvOptimizationRecord(**data)

    def get_cv_transformation_plan(
        self,
        job_posting_identifier: str,
        cv_optimization_identifier: str,
    ) -> Optional[CvTransformationPlan]:
        """
        Load a transformation plan from the filesystem.

        Args:
            job_posting_identifier: Identifier of the parent job posting
            cv_optimization_identifier: Identifier of the cv_optimization

        Returns:
            CvTransformationPlan or None if not found
        """
        plan_path = (
            self._cv_optimization_dir(
                job_posting_identifier, cv_optimization_identifier
            )
            / "transformation-plan.json"
        )

        if not plan_path.exists():
            return None

        with open(plan_path, "r") as f:
            data = json.load(f)

        return CvTransformationPlan(**data)

    def purge_cv_optimization(
        self,
        job_posting_identifier: str,
        identifier: str,
    ) -> bool:
        """
        Delete a cv_optimization directory entirely.

        Args:
            job_posting_identifier: Identifier of the parent job posting
            identifier: Identifier of the optimization

        Returns:
            True if deleted, False if not found
        """
        import shutil

        optimization_dir = self._cv_optimization_dir(job_posting_identifier, identifier)

        if not optimization_dir.exists():
            return False

        shutil.rmtree(optimization_dir)
        return True
