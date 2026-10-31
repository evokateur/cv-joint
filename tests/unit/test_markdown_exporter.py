"""Record front matter composed by the Markdown exporter."""

from datetime import datetime

import pytest
import yaml

from models import (
    CoverLetterRecord,
    CurriculumVitaeRecord,
    JobPostingRecord,
    OptimizedCvRecord,
)
from repositories import FileSystemRepository
from services.converters import MarkdownConverter
from services.exporters import MarkdownExporter


@pytest.fixture
def exporter(tmp_path):
    return MarkdownExporter(FileSystemRepository(str(tmp_path)), MarkdownConverter())


@pytest.fixture
def record():
    return JobPostingRecord(
        identifier="acme-swe",
        path="job-postings/acme-swe",
        company="Acme",
        title="Engineer",
        created_at=datetime(2026, 10, 30),
        experience_level="Senior",
        updated_at=datetime(2026, 10, 30),
    )


def test_composes_record_frontmatter(exporter, record):
    content = exporter.compose_document(record, "job-posting.md", "# Acme\n")
    _, metadata, body = content.split("---\n", 2)
    assert yaml.safe_load(metadata)["identifier"] == "acme-swe"
    assert body == "# Acme\n"


def test_patches_metadata_preserving_custom_keys_and_body(exporter, record):
    exporter.repository.add_document(
        record,
        "job-posting.md",
        "---\nidentifier: old\ncustom_tag: keep-me\n---\n# Hand-edited\n\nBody.\n",
    )
    exporter.patch_document_frontmatter(record)
    content = exporter.repository.load_document(record, "job-posting.md")
    _, metadata, body = content.split("---\n", 2)
    assert yaml.safe_load(metadata)["identifier"] == "acme-swe"
    assert yaml.safe_load(metadata)["custom_tag"] == "keep-me"
    assert body == "# Hand-edited\n\nBody.\n"


@pytest.mark.parametrize(
    "content", [None, "# No front matter\n", "---\ncustom: unfinished\n"]
)
def test_patch_skips_missing_or_undelimited_frontmatter(exporter, record, content):
    if content is not None:
        exporter.repository.add_document(record, "job-posting.md", content)
    exporter.patch_document_frontmatter(record)
    if content is None:
        assert not exporter.repository.document_exists(record, "job-posting.md")
    else:
        assert exporter.repository.load_document(record, "job-posting.md") == content


@pytest.mark.parametrize(
    "record_class, fields, filename",
    [
        (
            CurriculumVitaeRecord,
            {"name": "Jane", "profession": "Engineer"},
            "curriculum-vitae.md",
        ),
        (
            OptimizedCvRecord,
            {
                "name": "Jane",
                "profession": "Engineer",
                "job_posting_identifier": "acme-swe",
            },
            "curriculum-vitae.md",
        ),
        (
            OptimizedCvRecord,
            {
                "name": "Jane",
                "profession": "Engineer",
                "job_posting_identifier": "acme-swe",
            },
            "cv-transformation-plan.md",
        ),
        (CoverLetterRecord, {"name": "Jane"}, "cover-letter.md"),
    ],
)
def test_composes_other_record_documents(exporter, record_class, fields, filename):
    record = record_class(
        identifier="jane",
        path="stored/jane",
        created_at=datetime(2026, 10, 30),
        updated_at=datetime(2026, 10, 30),
        **fields,
    )
    content = exporter.compose_document(record, filename, "# Body\n")
    _, metadata, body = content.split("---\n", 2)
    assert yaml.safe_load(metadata)["identifier"] == "jane"
    assert yaml.safe_load(metadata)["path"] == "stored/jane"
    assert body == "# Body\n"


@pytest.mark.parametrize(
    "filename", ["readme.md", "job-posting.txt", "curriculum-vitae.md"]
)
def test_leaves_unowned_documents_unchanged(exporter, record, filename):
    content = "---\ncustom: keep\n---\n# Notes\n"
    assert exporter.compose_document(record, filename, content) == content
