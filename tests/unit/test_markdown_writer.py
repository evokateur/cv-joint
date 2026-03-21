"""
Unit tests for MarkdownWriter.
"""

import pytest
import tempfile
from pathlib import Path

from infrastructure import MarkdownWriter


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def writer(temp_dir):
    return MarkdownWriter(root_dir=temp_dir)


def _make_dir(temp_dir, *parts):
    path = Path(temp_dir).joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    (path / "content.md").write_text("# Content")
    return path


class TestMoveJobPosting:
    def test_moves_when_source_exists(self, writer, temp_dir):
        src = _make_dir(temp_dir, "job-postings", "old-id")
        writer.move_job_posting("old-id", "new-id")
        assert not src.exists()
        assert (Path(temp_dir) / "job-postings" / "new-id").exists()

    def test_no_op_when_already_moved(self, writer, temp_dir):
        _make_dir(temp_dir, "job-postings", "new-id")
        writer.move_job_posting("old-id", "new-id")  # should not raise

    def test_no_op_when_neither_exists(self, writer):
        writer.move_job_posting("old-id", "new-id")  # should not raise

    def test_raises_when_both_exist(self, writer, temp_dir):
        _make_dir(temp_dir, "job-postings", "old-id")
        _make_dir(temp_dir, "job-postings", "new-id")
        with pytest.raises(ValueError, match="Cannot move markdown"):
            writer.move_job_posting("old-id", "new-id")


class TestMoveCv:
    def test_moves_when_source_exists(self, writer, temp_dir):
        src = _make_dir(temp_dir, "cvs", "old-id")
        writer.move_cv("old-id", "new-id")
        assert not src.exists()
        assert (Path(temp_dir) / "cvs" / "new-id").exists()

    def test_no_op_when_already_moved(self, writer, temp_dir):
        _make_dir(temp_dir, "cvs", "new-id")
        writer.move_cv("old-id", "new-id")  # should not raise

    def test_no_op_when_neither_exists(self, writer):
        writer.move_cv("old-id", "new-id")  # should not raise

    def test_raises_when_both_exist(self, writer, temp_dir):
        _make_dir(temp_dir, "cvs", "old-id")
        _make_dir(temp_dir, "cvs", "new-id")
        with pytest.raises(ValueError, match="Cannot move markdown"):
            writer.move_cv("old-id", "new-id")


class TestMoveCvOptimization:
    def test_moves_when_source_exists(self, writer, temp_dir):
        src = _make_dir(temp_dir, "job-postings", "acme-swe", "cvs", "old-id")
        writer.move_cv_optimization("acme-swe", "old-id", "new-id")
        assert not src.exists()
        assert (Path(temp_dir) / "job-postings" / "acme-swe" / "cvs" / "new-id").exists()

    def test_no_op_when_already_moved(self, writer, temp_dir):
        _make_dir(temp_dir, "job-postings", "acme-swe", "cvs", "new-id")
        writer.move_cv_optimization("acme-swe", "old-id", "new-id")  # should not raise

    def test_no_op_when_neither_exists(self, writer):
        writer.move_cv_optimization("acme-swe", "old-id", "new-id")  # should not raise

    def test_raises_when_both_exist(self, writer, temp_dir):
        _make_dir(temp_dir, "job-postings", "acme-swe", "cvs", "old-id")
        _make_dir(temp_dir, "job-postings", "acme-swe", "cvs", "new-id")
        with pytest.raises(ValueError, match="Cannot move markdown"):
            writer.move_cv_optimization("acme-swe", "old-id", "new-id")
