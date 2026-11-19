"""
Unit tests for CLI commands.
"""

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
