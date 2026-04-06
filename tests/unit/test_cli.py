"""
Unit tests for CLI commands.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from ui.cli import main


class TestArchiveCommand:
    def test_calls_service(self):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            with patch("sys.argv", ["cv-joint", "archive", "job-postings/acme-swe"]):
                main()
        mock_service.archive_job_posting.assert_called_once_with("acme-swe")

    def test_prints_confirmation(self, capsys):
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value = MagicMock()
            with patch("sys.argv", ["cv-joint", "archive", "job-postings/acme-swe"]):
                main()
        assert "acme-swe" in capsys.readouterr().out

    def test_unrecognised_uri_exits(self):
        with patch("services.application.ApplicationService"):
            with patch("sys.argv", ["cv-joint", "archive", "cvs/my-cv"]):
                with pytest.raises(SystemExit):
                    main()


class TestListCommand:
    def test_lists_active_job_postings(self, capsys):
        mock_service = MagicMock()
        mock_service.get_job_postings.return_value = [
            {"identifier": "acme-swe", "company": "Acme", "title": "SWE", "created_at": "2025-01-15T00:00:00"},
        ]
        with patch("services.application.ApplicationService", return_value=mock_service):
            with patch("sys.argv", ["cv-joint", "list", "job-postings"]):
                main()
        mock_service.get_job_postings.assert_called_once_with(archived=False)
        assert "acme-swe" in capsys.readouterr().out

    def test_archived_flag_shows_only_archived(self, capsys):
        mock_service = MagicMock()
        mock_service.get_job_postings.return_value = [
            {"identifier": "old-job", "company": "Gone", "title": "Dev", "created_at": "2025-01-15T00:00:00", "is_archived": True},
            {"identifier": "active-job", "company": "Here", "title": "Dev", "created_at": "2025-02-01T00:00:00", "is_archived": False},
        ]
        with patch("services.application.ApplicationService", return_value=mock_service):
            with patch("sys.argv", ["cv-joint", "list", "job-postings", "--archived"]):
                main()
        out = capsys.readouterr().out
        assert "old-job" in out
        assert "active-job" not in out

    def test_unknown_collection_exits(self):
        with patch("sys.argv", ["cv-joint", "list", "cvs"]):
            with pytest.raises(SystemExit):
                main()


class TestApplyCommand:
    def test_calls_service(self):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            with patch("sys.argv", ["cv-joint", "apply", "job-postings/acme-swe", "my-cv"]):
                main()
        mock_service.mark_applied.assert_called_once_with("acme-swe", "my-cv", applied_at=None)

    def test_with_date(self):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            with patch(
                "sys.argv",
                ["cv-joint", "apply", "job-postings/acme-swe", "my-cv", "--date", "2025-01-15"],
            ):
                main()
        mock_service.mark_applied.assert_called_once_with(
            "acme-swe", "my-cv", applied_at=datetime(2025, 1, 15)
        )

    def test_prints_confirmation(self, capsys):
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value = MagicMock()
            with patch("sys.argv", ["cv-joint", "apply", "job-postings/acme-swe", "my-cv"]):
                main()
        assert "acme-swe" in capsys.readouterr().out

    def test_unrecognised_uri_exits(self):
        with patch("services.application.ApplicationService"):
            with patch("sys.argv", ["cv-joint", "apply", "cvs/my-cv", "my-cv"]):
                with pytest.raises(SystemExit):
                    main()
