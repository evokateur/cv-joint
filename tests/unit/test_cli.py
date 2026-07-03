"""
Unit tests for CLI commands.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ui.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestArchiveCommand:
    def test_calls_service(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(main, ["archive", "job-postings/acme-swe"])
        assert result.exit_code == 0
        mock_service.archive_job_posting.assert_called_once_with("acme-swe")

    def test_prints_confirmation(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value = MagicMock()
            result = runner.invoke(main, ["archive", "job-postings/acme-swe"])
        assert "acme-swe" in result.output

    def test_unrecognised_uri_exits(self, runner):
        with patch("services.application.ApplicationService"):
            result = runner.invoke(main, ["archive", "cvs/my-cv"])
        assert result.exit_code != 0


class TestListCommand:
    def test_lists_active_job_postings(self, runner):
        mock_service = MagicMock()
        mock_service.get_job_postings.return_value = [
            {"identifier": "acme-swe", "company": "Acme", "title": "SWE", "created_at": "2025-01-15T00:00:00"},
        ]
        with patch("services.application.ApplicationService", return_value=mock_service):
            result = runner.invoke(main, ["list", "job-postings"])
        assert result.exit_code == 0
        mock_service.get_job_postings.assert_called_once_with(location=None, all=False, query=None)
        assert "job-postings/acme-swe" in result.output

    def test_location_subpath_filters_by_location(self, runner):
        mock_service = MagicMock()
        mock_service.get_job_postings.return_value = [
            {"identifier": "old-job", "company": "Gone", "title": "Dev", "created_at": "2025-01-15T00:00:00"},
        ]
        with patch("services.application.ApplicationService", return_value=mock_service):
            result = runner.invoke(main, ["list", "job-postings/applied"])
        assert result.exit_code == 0
        mock_service.get_job_postings.assert_called_once_with(location="applied", all=False, query=None)
        assert "job-postings/old-job" in result.output

    def test_all_flag_returns_all_locations(self, runner):
        mock_service = MagicMock()
        mock_service.get_job_postings.return_value = []
        with patch("services.application.ApplicationService", return_value=mock_service):
            result = runner.invoke(main, ["list", "job-postings", "--recursive"])
        assert result.exit_code == 0
        mock_service.get_job_postings.assert_called_once_with(location=None, all=True, query=None)

    def test_all_flag_no_op_with_location_subpath(self, runner):
        mock_service = MagicMock()
        mock_service.get_job_postings.return_value = []
        with patch("services.application.ApplicationService", return_value=mock_service):
            result = runner.invoke(main, ["list", "job-postings/applied", "--recursive"])
        assert result.exit_code == 0
        mock_service.get_job_postings.assert_called_once_with(location="applied", all=True, query=None)

    def test_unknown_collection_exits(self, runner):
        result = runner.invoke(main, ["list", "dogs"])
        assert result.exit_code != 0


class TestCompleteCollection:
    def test_offers_base_collections(self, runner):
        with patch("ui.cli._load_collection", return_value=[]):
            from ui.cli import _complete_collection
            results = [item.value for item in _complete_collection(None, None, "")]
        assert "job-postings" in results
        assert "cvs" in results
        assert "curriculum-vitae" in results

    def test_offers_location_subpaths_from_index(self, runner):
        records = [{"location": "applied"}, {"location": "archived"}, {"location": None}]
        with patch("ui.cli._load_collection", return_value=records):
            from ui.cli import _complete_collection
            results = [item.value for item in _complete_collection(None, None, "job-postings/")]
        assert "job-postings/applied" in results
        assert "job-postings/archived" in results

    def test_filters_by_incomplete_prefix(self, runner):
        records = [{"location": "applied"}, {"location": "archived"}]
        with patch("ui.cli._load_collection", return_value=records):
            from ui.cli import _complete_collection
            results = [item.value for item in _complete_collection(None, None, "job-postings/app")]
        assert "job-postings/applied" in results
        assert "job-postings/archived" not in results


class TestApplyCommand:
    def test_calls_service(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(main, ["apply", "job-postings/acme-swe", "my-cv"])
        assert result.exit_code == 0
        mock_service.mark_applied.assert_called_once_with("acme-swe", "my-cv", applied_at=None)

    def test_with_date(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(main, ["apply", "job-postings/acme-swe", "my-cv", "--date", "2025-01-15"])
        assert result.exit_code == 0
        mock_service.mark_applied.assert_called_once_with(
            "acme-swe", "my-cv", applied_at=datetime(2025, 1, 15)
        )

    def test_prints_confirmation(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value = MagicMock()
            result = runner.invoke(main, ["apply", "job-postings/acme-swe", "my-cv"])
        assert "acme-swe" in result.output

    def test_full_composite_cv_identifier(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(main, ["apply", "job-postings/acme-swe", "acme-swe/my-cv"])
        assert result.exit_code == 0
        mock_service.mark_applied.assert_called_once_with("acme-swe", "acme-swe/my-cv", applied_at=None)

    def test_normalises_base_cv_uri(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(main, ["apply", "job-postings/acme-swe", "cvs/my-cv"])
        assert result.exit_code == 0
        mock_service.mark_applied.assert_called_once_with("acme-swe", "my-cv", applied_at=None)

    def test_normalises_optimized_cv_uri(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(main, ["apply", "job-postings/acme-swe", "job-postings/acme-swe/cvs/my-cv"])
        assert result.exit_code == 0
        mock_service.mark_applied.assert_called_once_with("acme-swe", "acme-swe/my-cv", applied_at=None)

    def test_unrecognised_uri_exits(self, runner):
        with patch("services.application.ApplicationService"):
            result = runner.invoke(main, ["apply", "cvs/my-cv", "my-cv"])
        assert result.exit_code != 0


class TestTransitionCommand:
    def test_calls_service(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(main, ["transition", "job-postings/acme-swe", "applied"])
        assert result.exit_code == 0
        mock_service.transition_job_posting.assert_called_once_with("acme-swe", "applied", None)

    def test_with_fields(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(main, ["transition", "job-postings/acme-swe", "applied",
                                          "--field", "note=great role"])
        assert result.exit_code == 0
        mock_service.transition_job_posting.assert_called_once_with(
            "acme-swe", "applied", {"note": "great role"}
        )

    def test_prints_confirmation(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value = MagicMock()
            result = runner.invoke(main, ["transition", "job-postings/acme-swe", "applied"])
        assert "acme-swe" in result.output
        assert "applied" in result.output

    def test_unrecognised_uri_exits(self, runner):
        with patch("services.application.ApplicationService"):
            result = runner.invoke(main, ["transition", "cvs/my-cv", "applied"])
        assert result.exit_code != 0


class TestUnarchiveCommand:
    def test_calls_service(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(main, ["unarchive", "job-postings/acme-swe"])
        assert result.exit_code == 0
        mock_service.unarchive_job_posting.assert_called_once_with("acme-swe")

    def test_prints_confirmation(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value = MagicMock()
            result = runner.invoke(main, ["unarchive", "job-postings/acme-swe"])
        assert "acme-swe" in result.output

    def test_unrecognised_uri_exits(self, runner):
        with patch("services.application.ApplicationService"):
            result = runner.invoke(main, ["unarchive", "cvs/my-cv"])
        assert result.exit_code != 0
