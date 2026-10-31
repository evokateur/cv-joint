"""
Pytest configuration and fixtures.
"""

from datetime import datetime

import pytest
from dotenv import load_dotenv

from models import (
    CoverLetterRecord,
    CurriculumVitaeRecord,
    JobPostingRecord,
    OptimizedCvRecord,
)

# Load environment variables from .env for all tests
load_dotenv()

CREATED_AT = datetime(2026, 1, 1)


@pytest.fixture
def build_job_posting_record():
    """Build an unpersisted JobPostingRecord; keyword arguments override defaults."""

    def build(identifier: str, **fields) -> JobPostingRecord:
        return JobPostingRecord(
            **{
                "identifier": identifier,
                "url": "https://example.com/job/123",
                "company": "Acme Corp",
                "title": "Software Engineer",
                "experience_level": "Mid-level",
                "created_at": CREATED_AT,
                "updated_at": CREATED_AT,
                **fields,
            }
        )

    return build


@pytest.fixture
def build_cv_record():
    """Build an unpersisted CurriculumVitaeRecord; keyword arguments override defaults."""

    def build(identifier: str, **fields) -> CurriculumVitaeRecord:
        return CurriculumVitaeRecord(
            **{
                "identifier": identifier,
                "name": "Jane Doe",
                "profession": "Software Engineer",
                "created_at": CREATED_AT,
                "updated_at": CREATED_AT,
                **fields,
            }
        )

    return build


@pytest.fixture
def build_optimized_cv_record():
    """Build an unpersisted OptimizedCvRecord; keyword arguments override defaults."""

    def build(
        identifier: str,
        job_posting_identifier: str = "acme-swe",
        base_cv_identifier: str | None = "jane-doe",
        **fields,
    ) -> OptimizedCvRecord:
        return OptimizedCvRecord(
            **{
                "identifier": identifier,
                "job_posting_identifier": job_posting_identifier,
                "base_cv_identifier": base_cv_identifier,
                "name": "Jane Doe",
                "profession": "Software Engineer",
                "created_at": CREATED_AT,
                "updated_at": CREATED_AT,
                **fields,
            }
        )

    return build


@pytest.fixture
def build_cover_letter_record():
    """Build an unpersisted CoverLetterRecord; keyword arguments override defaults."""

    def build(identifier: str, **fields) -> CoverLetterRecord:
        return CoverLetterRecord(
            **{
                "identifier": identifier,
                "name": "Wesley Hinkle",
                "company": "FrobozzCo",
                "position": "Sr. Magic Gunk Developer",
                "created_at": CREATED_AT,
                "updated_at": CREATED_AT,
                **fields,
            }
        )

    return build
