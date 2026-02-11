import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from models import (
    JobPosting,
    JobPostingRecord,
    CurriculumVitae,
    CurriculumVitaeRecord,
    CvOptimizationRecord,
    CvTransformationPlan,
)


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

    def get_absolute_path(self, collection_name: str, identifier: str) -> Path:
        if collection_name not in self.FILE_NAMES:
            raise ValueError(f"Unknown collection: {collection_name}")

        relative_path = self._generate_relative_path(collection_name, identifier)
        return self._resolve_path(relative_path)

    def get_cv_optimization_dir(
        self, job_posting_identifier: str, identifier: str
    ) -> Path:
        return self._cv_optimization_dir(job_posting_identifier, identifier)

    def _generate_relative_path(self, collection_name: str, identifier: str) -> str:
        """Generate default relative file path for a domain object."""
        filename = self.FILE_NAMES.get(collection_name, f"{collection_name}.json")
        return f"{collection_name}/{identifier}/{filename}"

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

    def add_cv(self, cv: CurriculumVitae, identifier: str) -> CurriculumVitaeRecord:
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

    def list_cv_data_files(self) -> list[dict[str, Any]]:
        """
        List the absolute file paths for all CVs, base and optimized.
        """
        results = []

        job_postings_root = self.data_dir / "job-postings"
        if job_postings_root.exists():
            job_posting_dirs = [d for d in job_postings_root.iterdir() if d.is_dir()]
        else:
            job_posting_dirs = []

        for job_posting_dir in job_posting_dirs:
            cv_optimizations_dir = job_posting_dir / "cv-optimizations"

            if not cv_optimizations_dir.exists():
                continue

            for optimization_dir in cv_optimizations_dir.iterdir():
                if not optimization_dir.is_dir():
                    continue

                record_path = optimization_dir / "record.json"
                if not record_path.exists():
                    continue

                with open(record_path, "r") as f:
                    record_data = json.load(f)

                separator = "."
                cv_path = optimization_dir / "cv.json"
                result = {
                    "identifier": separator.join(
                        [
                            job_posting_dir.name,
                            optimization_dir.name,
                            record_data.get("base_cv_identifier"),
                        ]
                    ),
                    "filepath": str(self._resolve_path(cv_path.name)),
                }

                results.append(result)

        collection = self._load_collection(self.cvs_collection)
        for item in collection:
            results.append(
                {
                    "identifier": item.get("identifier"),
                    "filepath": str(self._resolve_path(item.get("filepath"))),
                }
            )

        return results

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
        identifier: str,
        base_cv_identifier: str,
    ) -> CvOptimizationRecord:
        """
        Persist CV optimization record.

        The transformation plan and optimized CV files are assumed to already exist.

        Args:
            identifier: Unique identifier for this optimization
            job_posting_identifier: Identifier of the parent job posting
            base_cv_identifier: Identifier of the CV being optimized

        Returns:
            The persisted CvOptimizationRecord
        """
        optimization_dir = self._cv_optimization_dir(job_posting_identifier, identifier)
        optimization_dir.mkdir(parents=True, exist_ok=True)

        record = CvOptimizationRecord(
            identifier=identifier,
            job_posting_identifier=job_posting_identifier,
            base_cv_identifier=base_cv_identifier,
            created_at=datetime.now(),
        )

        record_path = optimization_dir / "record.json"
        with open(record_path, "w") as f:
            json.dump(record.model_dump(mode="json"), f, indent=2)

        return record

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

            for optimization_dir in cv_optimizations_dir.iterdir():
                if not optimization_dir.is_dir():
                    continue

                record_path = optimization_dir / "record.json"
                if not record_path.exists():
                    continue

                with open(record_path, "r") as f:
                    record_data = json.load(f)

                result = {
                    "job_posting_identifier": record_data.get("job_posting_identifier"),
                    "identifier": record_data.get("identifier"),
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
        Load CV optimization record from record.json.

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
        optimization_identifier: str,
    ) -> Optional[CvTransformationPlan]:
        """
        Load a transformation plan from the filesystem.

        Args:
            job_posting_identifier: Identifier of the parent job posting
            optimization_identifier: Identifier of the cv_optimization

        Returns:
            CvTransformationPlan or None if not found
        """
        plan_path = (
            self._cv_optimization_dir(job_posting_identifier, optimization_identifier)
            / "transformation-plan.json"
        )

        if not plan_path.exists():
            return None

        with open(plan_path, "r") as f:
            data = json.load(f)

        return CvTransformationPlan(**data)

    def get_optimized_cv(
        self, job_posting_identifier: str, cv_optimization_identifier: str
    ) -> Optional[CurriculumVitae]:
        cv_path = (
            self._cv_optimization_dir(
                job_posting_identifier, cv_optimization_identifier
            )
            / "cv.json"
        )

        if not cv_path.exists():
            return None

        with open(cv_path, "r") as f:
            data = json.load(f)

        return CurriculumVitae(**data)

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
