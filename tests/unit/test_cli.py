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


class TestAnalyzeJobPostingCommand:
    def test_url_only_fetches_content(self, runner):
        url = "https://example.com/job"
        mock_record = MagicMock()
        mock_record.identifier = "acme-swe"
        with patch("services.application.ApplicationService") as MockService:
            svc = MockService.return_value
            svc.analyze_job_posting.return_value = {}
            svc.generate_default_identifier.return_value = "acme-swe"
            svc.add_job_posting.return_value = mock_record
            result = runner.invoke(main, ["ingest", "job-posting", url])
        assert result.exit_code == 0, result.output
        svc.analyze_job_posting.assert_called_once_with(url, None)
        assert "job-postings/acme-swe" in result.output

    def test_url_with_content_file(self, runner, tmp_path):
        url = "https://example.com/job"
        content = tmp_path / "job.md"
        content.write_text("# Job")
        mock_record = MagicMock()
        mock_record.identifier = "acme-swe"
        with patch("services.application.ApplicationService") as MockService:
            svc = MockService.return_value
            svc.analyze_job_posting.return_value = {}
            svc.generate_default_identifier.return_value = "acme-swe"
            svc.add_job_posting.return_value = mock_record
            result = runner.invoke(main, ["ingest", "job-posting", url, str(content)])
        assert result.exit_code == 0, result.output
        svc.analyze_job_posting.assert_called_once_with(url, str(content))
        assert "job-postings/acme-swe" in result.output

    def test_stdin_content_buffers_to_tempfile(self, runner):
        url = "https://example.com/job"
        mock_record = MagicMock()
        mock_record.identifier = "acme-swe"
        with patch("services.application.ApplicationService") as MockService:
            svc = MockService.return_value
            svc.analyze_job_posting.return_value = {}
            svc.generate_default_identifier.return_value = "acme-swe"
            svc.add_job_posting.return_value = mock_record
            result = runner.invoke(
                main, ["ingest", "job-posting", url, "-"], input="# Job Posting"
            )
        assert result.exit_code == 0, result.output
        args = svc.analyze_job_posting.call_args.args
        assert args[0] == url
        assert args[1] is not None

    def test_missing_url_exits_nonzero(self, runner):
        with patch("services.application.ApplicationService"):
            result = runner.invoke(main, ["ingest", "job-posting"])
        assert result.exit_code != 0

    def test_service_error_exits_nonzero(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value.analyze_job_posting.side_effect = ValueError(
                "analysis failed"
            )
            result = runner.invoke(
                main, ["ingest", "job-posting", "https://example.com"]
            )
        assert result.exit_code != 0
        assert "analysis failed" in result.output


class TestAnalyzeCvCommand:
    def test_file_calls_service_with_content_file(self, runner, tmp_path):
        content = tmp_path / "cv.yaml"
        content.write_text("name: Jane")
        mock_record = MagicMock()
        mock_record.identifier = "jane-doe"
        with patch("services.application.ApplicationService") as MockService:
            svc = MockService.return_value
            svc.analyze_cv.return_value = {}
            svc.generate_default_identifier.return_value = "jane-doe"
            svc.add_cv.return_value = mock_record
            result = runner.invoke(main, ["ingest", "cv", str(content)])
        assert result.exit_code == 0, result.output
        svc.analyze_cv.assert_called_once_with(str(content))
        assert "cvs/jane-doe" in result.output

    def test_stdin_buffers_to_tempfile(self, runner):
        mock_record = MagicMock()
        mock_record.identifier = "jane-doe"
        with patch("services.application.ApplicationService") as MockService:
            svc = MockService.return_value
            svc.analyze_cv.return_value = {}
            svc.generate_default_identifier.return_value = "jane-doe"
            svc.add_cv.return_value = mock_record
            result = runner.invoke(main, ["ingest", "cv", "-"], input="name: Jane")
        assert result.exit_code == 0, result.output
        args = svc.analyze_cv.call_args.args
        assert args[0] is not None

    def test_service_error_exits_nonzero(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value.analyze_cv.side_effect = ValueError(
                "content_file must be provided"
            )
            result = runner.invoke(main, ["ingest", "cv", "-"], input="")
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


class TestAddCommand:
    def test_calls_service(self, runner, tmp_path):
        source = tmp_path / "notes.md"
        source.write_text("# Notes")
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value.add_document.return_value = (
                "job-postings/acme-swe/notes.md"
            )
            result = runner.invoke(main, ["add", "job-postings/acme-swe", str(source)])
        assert result.exit_code == 0
        MockService.return_value.add_document.assert_called_once_with(
            "job-postings/acme-swe", str(source)
        )

    def test_prints_doc_uri(self, runner, tmp_path):
        source = tmp_path / "notes.md"
        source.write_text("# Notes")
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value.add_document.return_value = (
                "job-postings/acme-swe/notes.md"
            )
            result = runner.invoke(main, ["add", "job-postings/acme-swe", str(source)])
        assert "job-postings/acme-swe/notes.md" in result.output

    def test_not_found_exits(self, runner, tmp_path):
        source = tmp_path / "notes.md"
        source.write_text("# Notes")
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value.add_document.side_effect = ValueError(
                "Not found: job-postings/acme-swe"
            )
            result = runner.invoke(main, ["add", "job-postings/acme-swe", str(source)])
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
