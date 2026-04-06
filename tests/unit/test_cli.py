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
