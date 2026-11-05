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


class TestApplyCommand:
    def test_calls_service(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(main, ["apply", "job-postings/acme-swe", "my-cv"])
        assert result.exit_code == 0
        mock_service.mark_applied.assert_called_once_with(
            "acme-swe", "my-cv", applied_at=None
        )

    def test_with_date(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(
                main,
                ["apply", "job-postings/acme-swe", "my-cv", "--date", "2025-01-15"],
            )
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
            result = runner.invoke(
                main, ["apply", "job-postings/acme-swe", "acme-swe/my-cv"]
            )
        assert result.exit_code == 0
        mock_service.mark_applied.assert_called_once_with(
            "acme-swe", "acme-swe/my-cv", applied_at=None
        )

    def test_normalizes_base_cv_uri(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(
                main, ["apply", "job-postings/acme-swe", "cvs/my-cv"]
            )
        assert result.exit_code == 0
        mock_service.mark_applied.assert_called_once_with(
            "acme-swe", "my-cv", applied_at=None
        )

    def test_normalizes_optimized_cv_uri(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(
                main,
                ["apply", "job-postings/acme-swe", "job-postings/acme-swe/cvs/my-cv"],
            )
        assert result.exit_code == 0
        mock_service.mark_applied.assert_called_once_with(
            "acme-swe", "acme-swe/my-cv", applied_at=None
        )

    def test_unrecognised_uri_exits(self, runner):
        with patch("services.application.ApplicationService"):
            result = runner.invoke(main, ["apply", "cvs/my-cv", "my-cv"])
        assert result.exit_code != 0


class TestTransitionCommand:
    def test_calls_service(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(
                main, ["transition", "job-postings/acme-swe", "applied"]
            )
        assert result.exit_code == 0
        mock_service.transition_job_posting.assert_called_once_with(
            "acme-swe", "applied", None
        )

    def test_with_fields(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(
                main,
                [
                    "transition",
                    "job-postings/acme-swe",
                    "applied",
                    "--field",
                    "note=great role",
                ],
            )
        assert result.exit_code == 0
        mock_service.transition_job_posting.assert_called_once_with(
            "acme-swe", "applied", {"note": "great role"}
        )

    def test_prints_confirmation(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value = MagicMock()
            result = runner.invoke(
                main, ["transition", "job-postings/acme-swe", "applied"]
            )
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


class TestRenameCommand:
    def test_bare_identifier_passes_through(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(
                main, ["rename", "job-postings/acme-swe", "acme-swe-2"]
            )
        assert result.exit_code == 0, result.output
        mock_service.rename_job_posting.assert_called_once_with(
            "acme-swe", "acme-swe-2"
        )

    def test_normalizes_matching_collection_prefix(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(
                main, ["rename", "job-postings/acme-swe", "job-postings/acme-swe-2"]
            )
        assert result.exit_code == 0, result.output
        mock_service.rename_job_posting.assert_called_once_with(
            "acme-swe", "acme-swe-2"
        )

    def test_normalizes_matching_cv_prefix(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(main, ["rename", "cvs/acme-swe", "cvs/acme-swe-2"])
        assert result.exit_code == 0, result.output
        mock_service.rename_cv.assert_called_once_with("acme-swe", "acme-swe-2")

    def test_normalizes_matching_optimized_cv_prefix(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(
                main,
                ["rename", "job-postings/acme/cvs/foo", "job-postings/acme/cvs/bar"],
            )
        assert result.exit_code == 0, result.output
        mock_service.rename_optimized_cv.assert_called_once_with("acme", "foo", "bar")

    def test_rejects_wrong_collection_prefix(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(
                main, ["rename", "job-postings/acme-swe", "cvs/acme-swe-2"]
            )
        assert result.exit_code != 0
        assert "illegal new identifier" in result.output
        mock_service.rename_job_posting.assert_not_called()


class TestExportSchemaCommand:
    def test_explicit_path_writes_schema_files(self, runner, tmp_path):
        result = runner.invoke(main, ["export-schema", str(tmp_path)])
        assert result.exit_code == 0
        written = {p.name for p in tmp_path.iterdir()}
        assert "job-posting.schema.json" in written
        assert "curriculum-vitae.schema.json" in written
        assert "cv-transformation-plan.schema.json" in written

    def test_default_path_uses_configured_data_dir(self, runner, tmp_path):
        mock_settings = MagicMock()
        mock_settings.repositories.filesystem.data_dir = str(tmp_path)
        with patch("config.root.get_settings", return_value=mock_settings):
            result = runner.invoke(main, ["export-schema"])
        assert result.exit_code == 0
        assert (tmp_path / "schema" / "job-posting.schema.json").exists()
