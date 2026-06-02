import json
import os
import sys
from datetime import datetime
from pathlib import Path

import click
import yaml

from repositories.filesystem import parse_uri


def _load_collection(name: str) -> list[dict]:
    from config.settings import get_data_dir
    path = Path(get_data_dir()).expanduser() / "collections" / f"{name}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _complete_uri(_ctx, _param, incomplete):
    from click.shell_completion import CompletionItem
    candidates = (
        [f"job-postings/{item['identifier']}" for item in _load_collection("job-postings")]
        + [f"cvs/{item['identifier']}" for item in _load_collection("cvs")]
        + [
            f"job-postings/{item['job_posting_identifier']}/cvs/{item['identifier']}"
            for item in _load_collection("optimized-cvs")
            if item.get("job_posting_identifier") and item.get("identifier")
        ]
    )
    return [CompletionItem(c) for c in candidates if c.startswith(incomplete)]


def _complete_job_posting_uri(_ctx, _param, incomplete):
    from click.shell_completion import CompletionItem
    candidates = [f"job-postings/{item['identifier']}" for item in _load_collection("job-postings")]
    return [CompletionItem(c) for c in candidates if c.startswith(incomplete)]


def _complete_cv_identifier(ctx, _param, incomplete):
    from click.shell_completion import CompletionItem
    candidates = [f"cvs/{item['identifier']}" for item in _load_collection("cvs")]
    try:
        parsed = parse_uri(ctx.params.get("uri", ""))
        if parsed["collection"] == "job-postings":
            jp_id = parsed["identifier"]
            candidates += [
                f"cvs/{item['identifier']}"
                for item in _load_collection("optimized-cvs")
                if item.get("job_posting_identifier") == jp_id and item.get("identifier")
            ]
    except ValueError:
        pass
    return [CompletionItem(c) for c in candidates if c.startswith(incomplete)]


def _normalise_cv_identifier(value: str) -> str:
    try:
        parsed = parse_uri(value)
    except ValueError:
        return value
    if parsed["collection"] == "optimized-cvs":
        return f"{parsed['job_posting_identifier']}/{parsed['identifier']}"
    if parsed["collection"] == "cvs":
        return parsed["identifier"]
    return value


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """CV Joint application."""
    if ctx.invoked_subcommand is None:
        from ui.app import launch
        launch(inbrowser=False)


@main.command("open")
def cmd_open():
    """Start the Gradio server and open it in a browser."""
    from ui.app import launch
    launch(inbrowser=True)


@main.command("show-config")
def show_config():
    """Print merged configuration to stdout and exit."""
    from config.settings import get_merged_config
    config = get_merged_config()
    yaml.dump(config, sys.stdout, default_flow_style=False, sort_keys=False)


@main.command("export-markdown")
@click.argument("collection", required=False)
def export_markdown(collection):
    """Re-export markdown files from stored data and exit."""
    from services.application import ApplicationService
    service = ApplicationService()
    try:
        count = service.export_markdown(collection)
    except ValueError as e:
        raise click.UsageError(str(e))
    click.echo(f"Re-exported {count} markdown file(s)")


@main.command("remove")
@click.argument("uri", shell_complete=_complete_uri)
def remove(uri):
    """Remove an object by URI and exit."""
    from services.application import ApplicationService
    service = ApplicationService()
    try:
        parsed = parse_uri(uri)
    except ValueError:
        raise click.UsageError(
            f"unrecognised URI '{uri}'\n"
            "Expected: job-postings/{{id}}, cvs/{{id}}, or job-postings/{{id}}/cvs/{{id}}"
        )

    if parsed["collection"] == "optimized-cvs":
        removed = service.remove_cv_optimization(parsed["job_posting_identifier"], parsed["identifier"])
    elif parsed["collection"] == "job-postings":
        removed = service.remove_job_posting(parsed["identifier"])
    else:
        removed = service.remove_cv(parsed["identifier"])

    if removed:
        click.echo(f"Removed {uri}")
    else:
        click.echo(f"Not found: {uri}", err=True)
        sys.exit(1)


@main.command("reanalyze")
@click.argument("uri", shell_complete=_complete_uri)
@click.argument("content_file", required=False)
def reanalyze(uri, content_file):
    """Re-analyze an object by URI and overwrite the existing record."""
    from services.application import ApplicationService
    service = ApplicationService()
    try:
        parsed = parse_uri(uri)
    except ValueError:
        raise click.UsageError(
            f"unrecognised URI '{uri}'\n"
            "Expected: job-postings/{{id}}, cvs/{{id}}, or job-postings/{{id}}/cvs/{{id}}"
        )

    try:
        if parsed["collection"] == "job-postings":
            record = service.reanalyze_job_posting(parsed["identifier"], content_file)
            new_uri = f"job-postings/{record.identifier}"
        elif parsed["collection"] == "cvs":
            if not content_file:
                raise click.UsageError("reanalyze cvs/{id} requires CONTENT_FILE")
            record = service.reanalyze_cv(parsed["identifier"], content_file)
            new_uri = f"cvs/{record.identifier}"
        else:
            record = service.reanalyze_cv_optimization(parsed["job_posting_identifier"], parsed["identifier"])
            new_uri = f"job-postings/{record.job_posting_identifier}/cvs/{record.identifier}"
    except click.UsageError:
        raise
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Reanalyzed as {new_uri}")


@main.command("rename")
@click.argument("uri", shell_complete=_complete_uri)
@click.argument("new_id")
def rename(uri, new_id):
    """Rename an object by URI and exit."""
    from services.application import ApplicationService
    service = ApplicationService()
    try:
        parsed = parse_uri(uri)
    except ValueError:
        raise click.UsageError(
            f"unrecognised URI '{uri}'\n"
            "Expected: job-postings/{{id}}, cvs/{{id}}, or job-postings/{{id}}/cvs/{{id}}"
        )

    try:
        if parsed["collection"] == "job-postings":
            service.rename_job_posting(parsed["identifier"], new_id)
        elif parsed["collection"] == "cvs":
            service.rename_cv(parsed["identifier"], new_id)
        else:
            service.rename_cv_optimization(parsed["job_posting_identifier"], parsed["identifier"], new_id)
    except click.UsageError:
        raise
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Renamed {uri} to {new_id}")


@main.command("list")
@click.argument("collection", type=click.Choice(["job-postings", "cvs", "curriculum-vitae"]))
@click.option("--archived", is_flag=True, help="Show only archived entries")
@click.option("-q", "--query", metavar="QUERY", help="Filter by company, title, experience level, or URL")
def list_objects(collection, archived, query):
    """List objects by collection and exit."""
    from services.application import ApplicationService
    service = ApplicationService()

    if collection == "job-postings":
        if archived:
            jobs = [j for j in service.get_job_postings(archived=True, query=query) if j.get("is_archived")]
        else:
            jobs = service.get_job_postings(archived=False, query=query)
        for j in jobs:
            click.echo(f"job-postings/{j.get('identifier', '')}")
    elif collection in ("cvs", "curriculum-vitae"):
        for cv in service.get_cvs(query=query):
            click.echo(f"cvs/{cv.get('identifier', '')}")


@main.command("archive")
@click.argument("uri", shell_complete=_complete_job_posting_uri)
def archive(uri):
    """Archive a job posting by URI and exit."""
    from services.application import ApplicationService
    service = ApplicationService()
    try:
        parsed = parse_uri(uri)
    except ValueError:
        raise click.UsageError(f"unrecognised URI '{uri}'\nExpected: job-postings/{{id}}")

    if parsed["collection"] != "job-postings":
        raise click.UsageError(f"unrecognised URI '{uri}'\nExpected: job-postings/{{id}}")

    service.archive_job_posting(parsed["identifier"])
    click.echo(f"Archived {uri}")


@main.command("apply")
@click.argument("uri", shell_complete=_complete_job_posting_uri)
@click.argument("cv_identifier", shell_complete=_complete_cv_identifier)
@click.option("--date", metavar="YYYY-MM-DD", help="Application date (defaults to today)")
def apply(uri, cv_identifier, date):
    """Mark a job posting as applied to and exit."""
    from services.application import ApplicationService
    service = ApplicationService()
    try:
        parsed = parse_uri(uri)
    except ValueError:
        raise click.UsageError(f"unrecognised URI '{uri}'\nExpected: job-postings/{{id}}")

    if parsed["collection"] != "job-postings":
        raise click.UsageError(f"unrecognised URI '{uri}'\nExpected: job-postings/{{id}}")

    applied_at = datetime.strptime(date, "%Y-%m-%d") if date else None
    cv_identifier = _normalise_cv_identifier(cv_identifier)
    service.mark_applied(parsed["identifier"], cv_identifier, applied_at=applied_at)
    click.echo(f"Marked {uri} as applied with {cv_identifier}")


@main.command("completion")
@click.argument("shell", required=False, type=click.Choice(["bash", "zsh", "fish"]))
def completion(shell):
    """Print the shell completion script.

    \b
    Add to your shell config:
      source <(cv-joint completion)
    """
    if shell is None:
        shell = os.path.basename(os.environ.get("SHELL", ""))
    if shell not in ("bash", "zsh", "fish"):
        raise click.UsageError(f"Unknown shell {shell!r}. Supported: bash, zsh, fish")
    import subprocess
    result = subprocess.run(
        ["cv-joint"],
        env={**os.environ, "_CV_JOINT_COMPLETE": f"{shell}_source"},
        capture_output=True,
        text=True,
    )
    click.echo(result.stdout, nl=False)


if __name__ == "__main__":
    main()
