"""
User-specified identifier CLI machinery.
"""

import click
import pytest
from click.testing import CliRunner

from ui.identifier import identifier_option, resolve_identifier, validate_identifier


@pytest.fixture
def runner():
    return CliRunner()


def _make_command(taken, default, interactive):
    """A throwaway command mounting the shared option + resolver."""

    @click.command()
    @identifier_option
    def cmd(identifier):
        result = resolve_identifier(
            identifier, default, lambda i: i in taken, interactive=interactive
        )
        click.echo(f"RESULT={result}")

    return cmd


class TestValidateIdentifier:
    def test_passes_through_valid(self):
        assert validate_identifier("acme-swe") == "acme-swe"

    def test_passes_uppercase_verbatim(self):
        assert validate_identifier("Acme-SWE") == "Acme-SWE"

    @pytest.mark.parametrize("bad", ["", " ", "a b", "a/b", "cvs/foo", " acme"])
    def test_rejects_empty_whitespace_slash(self, bad):
        with pytest.raises(click.UsageError):
            validate_identifier(bad)


class TestExplicitIdentifier:
    def test_free_is_accepted(self, runner):
        result = runner.invoke(_make_command({"other"}, "d", True), ["-i", "acme-swe"])
        assert result.exit_code == 0, result.output
        assert "RESULT=acme-swe" in result.output

    def test_taken_errors(self, runner):
        result = runner.invoke(
            _make_command({"acme-swe"}, "d", True), ["-i", "acme-swe"]
        )
        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_invalid_errors_without_cleansing(self, runner):
        result = runner.invoke(_make_command(set(), "d", True), ["-i", "a/b"])
        assert result.exit_code != 0


class TestPrompt:
    def test_shows_collision_avoiding_default(self, runner):
        result = runner.invoke(_make_command(set(), "acme-swe-2", True), input="\n")
        assert result.exit_code == 0, result.output
        assert "[acme-swe-2]" in result.output
        assert "RESULT=acme-swe-2" in result.output

    def test_typed_value_accepted(self, runner):
        result = runner.invoke(
            _make_command(set(), "default-id", True), input="my-choice\n"
        )
        assert result.exit_code == 0, result.output
        assert "RESULT=my-choice" in result.output

    def test_reprompts_on_collision(self, runner):
        # first line collides -> error + re-prompt; second line is free
        result = runner.invoke(
            _make_command({"taken"}, "safe-default", True),
            input="taken\nfree-id\n",
        )
        assert result.exit_code == 0, result.output
        assert "Error" in result.output
        assert "RESULT=free-id" in result.output

    def test_reprompts_on_invalid(self, runner):
        result = runner.invoke(
            _make_command(set(), "safe-default", True),
            input="bad/value\ngood-value\n",
        )
        assert result.exit_code == 0, result.output
        assert "Error" in result.output
        assert "RESULT=good-value" in result.output


class TestNoDefault:
    def test_prompts_for_typed_value(self, runner):
        result = runner.invoke(_make_command(set(), None, True), input="chosen-id\n")
        assert result.exit_code == 0, result.output
        assert "RESULT=chosen-id" in result.output

    def test_reprompts_on_empty(self, runner):
        result = runner.invoke(
            _make_command(set(), None, True), input="\nchosen-id\n"
        )
        assert result.exit_code == 0, result.output
        assert "RESULT=chosen-id" in result.output

    def test_non_interactive_still_requires_identifier(self, runner):
        result = runner.invoke(_make_command(set(), None, False), [])
        assert result.exit_code != 0
        assert "--identifier is required" in result.output


class TestNonInteractive:
    def test_requires_identifier_when_no_tty(self, runner):
        result = runner.invoke(_make_command(set(), "d", False), [])
        assert result.exit_code != 0
        assert "--identifier is required" in result.output

    def test_explicit_identifier_still_works_without_tty(self, runner):
        result = runner.invoke(_make_command(set(), "d", False), ["-i", "chosen"])
        assert result.exit_code == 0, result.output
        assert "RESULT=chosen" in result.output
