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


class TestAnalyzeJobPostingCommand:
    def test_url_only_fetches_content(self, runner):
        url = "https://example.com/job"
        mock_record = MagicMock()
        mock_record.identifier = "acme-swe"
        with patch("services.application.ApplicationService") as MockService:
            svc = MockService.return_value
            svc.create_job_posting.return_value = ({}, "acme-swe", "# md")
            svc.save_job_posting.return_value = mock_record
            result = runner.invoke(main, ["analyze", "job-posting", url])
        assert result.exit_code == 0, result.output
        svc.create_job_posting.assert_called_once_with(url, None)
        assert "job-postings/acme-swe" in result.output

    def test_url_with_content_file(self, runner, tmp_path):
        url = "https://example.com/job"
        content = tmp_path / "job.md"
        content.write_text("# Job")
        mock_record = MagicMock()
        mock_record.identifier = "acme-swe"
        with patch("services.application.ApplicationService") as MockService:
            svc = MockService.return_value
            svc.create_job_posting.return_value = ({}, "acme-swe", "# md")
            svc.save_job_posting.return_value = mock_record
            result = runner.invoke(main, ["analyze", "job-posting", url, str(content)])
        assert result.exit_code == 0, result.output
        svc.create_job_posting.assert_called_once_with(url, str(content))
        assert "job-postings/acme-swe" in result.output

    def test_stdin_content_buffers_to_tempfile(self, runner):
        url = "https://example.com/job"
        mock_record = MagicMock()
        mock_record.identifier = "acme-swe"
        with patch("services.application.ApplicationService") as MockService:
            svc = MockService.return_value
            svc.create_job_posting.return_value = ({}, "acme-swe", "# md")
            svc.save_job_posting.return_value = mock_record
            result = runner.invoke(main, ["analyze", "job-posting", url, "-"], input="# Job Posting")
        assert result.exit_code == 0, result.output
        args = svc.create_job_posting.call_args.args
        assert args[0] == url
        assert args[1] is not None

    def test_missing_url_exits_nonzero(self, runner):
        with patch("services.application.ApplicationService"):
            result = runner.invoke(main, ["analyze", "job-posting"])
        assert result.exit_code != 0

    def test_service_error_exits_nonzero(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value.create_job_posting.side_effect = ValueError("already analyzed: foo")
            result = runner.invoke(main, ["analyze", "job-posting", "https://example.com"])
        assert result.exit_code != 0
        assert "already analyzed" in result.output


class TestAnalyzeCvCommand:
    def test_file_calls_service_with_content_file(self, runner, tmp_path):
        content = tmp_path / "cv.yaml"
        content.write_text("name: Jane")
        mock_record = MagicMock()
        mock_record.identifier = "jane-doe"
        with patch("services.application.ApplicationService") as MockService:
            svc = MockService.return_value
            svc.create_cv.return_value = ({}, "jane-doe")
            svc.save_cv.return_value = mock_record
            result = runner.invoke(main, ["analyze", "cv", str(content)])
        assert result.exit_code == 0, result.output
        svc.create_cv.assert_called_once_with(str(content))
        assert "cvs/jane-doe" in result.output

    def test_stdin_buffers_to_tempfile(self, runner):
        mock_record = MagicMock()
        mock_record.identifier = "jane-doe"
        with patch("services.application.ApplicationService") as MockService:
            svc = MockService.return_value
            svc.create_cv.return_value = ({}, "jane-doe")
            svc.save_cv.return_value = mock_record
            result = runner.invoke(main, ["analyze", "cv", "-"], input="name: Jane")
        assert result.exit_code == 0, result.output
        args = svc.create_cv.call_args.args
        assert args[0] is not None

    def test_service_error_exits_nonzero(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value.create_cv.side_effect = ValueError("content_file must be provided")
            result = runner.invoke(main, ["analyze", "cv", "-"], input="")
        assert result.exit_code != 0


class TestReanalyzeCommand:
    def test_job_posting_stdin_buffers_to_tempfile(self, runner):
        mock_record = MagicMock()
        mock_record.identifier = "acme-swe-2"
        with patch("services.application.ApplicationService") as MockService:
            svc = MockService.return_value
            svc.reanalyze_job_posting.return_value = mock_record
            result = runner.invoke(
                main, ["reanalyze", "job-postings/acme-swe", "-"], input="# Job Posting"
            )
        assert result.exit_code == 0, result.output
        args = svc.reanalyze_job_posting.call_args.args
        assert args[0] == "acme-swe"
        assert args[1] is not None and args[1] != "-"
        assert "job-postings/acme-swe-2" in result.output

    def test_job_posting_no_content_passes_none(self, runner):
        mock_record = MagicMock()
        mock_record.identifier = "acme-swe-2"
        with patch("services.application.ApplicationService") as MockService:
            svc = MockService.return_value
            svc.reanalyze_job_posting.return_value = mock_record
            result = runner.invoke(main, ["reanalyze", "job-postings/acme-swe"])
        assert result.exit_code == 0, result.output
        svc.reanalyze_job_posting.assert_called_once_with("acme-swe", None)


class TestRenameCommand:
    def test_normalises_matching_collection_prefix(self, runner):
        with patch("services.application.ApplicationService") as MockService:
            mock_service = MockService.return_value
            result = runner.invoke(
                main, ["rename", "job-postings/acme-swe", "job-postings/acme-swe-2"]
            )
        assert result.exit_code == 0, result.output
        mock_service.rename_job_posting.assert_called_once_with(
            "acme-swe", "acme-swe-2"
        )

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
            MockService.return_value.add_document.return_value = "job-postings/acme-swe/notes.md"
            result = runner.invoke(main, ["add", "job-postings/acme-swe", str(source)])
        assert result.exit_code == 0
        MockService.return_value.add_document.assert_called_once_with("job-postings/acme-swe", str(source))

    def test_prints_doc_uri(self, runner, tmp_path):
        source = tmp_path / "notes.md"
        source.write_text("# Notes")
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value.add_document.return_value = "job-postings/acme-swe/notes.md"
            result = runner.invoke(main, ["add", "job-postings/acme-swe", str(source)])
        assert "job-postings/acme-swe/notes.md" in result.output

    def test_not_found_exits(self, runner, tmp_path):
        source = tmp_path / "notes.md"
        source.write_text("# Notes")
        with patch("services.application.ApplicationService") as MockService:
            MockService.return_value.add_document.side_effect = ValueError("Not found: job-postings/acme-swe")
            result = runner.invoke(main, ["add", "job-postings/acme-swe", str(source)])
        assert result.exit_code != 0
