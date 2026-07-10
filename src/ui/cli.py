import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import click
import yaml

from repositories.filesystem import normalize_new_identifier, parse_uri


def _load_collection(name: str) -> list[dict]:
    from config.root import get_settings
    path = (
        Path(get_settings().repositories.filesystem.data_dir)
        / "collections"
        / f"{name}.json"
    )
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
    candidates = []
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
    candidates += [f"cvs/{item['identifier']}" for item in _load_collection("cvs")]
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
    from config.root import get_settings
    config = get_settings().model_dump(by_alias=True)
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
@click.argument("content_file", required=False, type=click.Path(dir_okay=False, allow_dash=True))
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

    content_file, is_temp = _resolve_content(content_file)
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
    finally:
        if is_temp and content_file:
            os.unlink(content_file)

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
        new_id = normalize_new_identifier(uri, new_id)
    except ValueError:
        raise click.UsageError(
            f"illegal new identifier '{new_id}'\n"
            "Expected a bare identifier (no '/'), optionally prefixed with the source collection"
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


def _complete_collection(_ctx, _param, incomplete):
    from click.shell_completion import CompletionItem
    base = ["job-postings", "cvs", "curriculum-vitae"]
    job_postings = _load_collection("job-postings")
    locations = sorted({item["location"] for item in job_postings if item.get("location")})
    candidates = (
        base
        + [f"job-postings/{loc}" for loc in locations]
        + [
            f"job-postings/{item['location']}/{item['identifier']}"
            for item in job_postings
            if item.get("location") and item.get("identifier")
        ]
    )
    return [CompletionItem(c) for c in candidates if c.startswith(incomplete)]


@main.command("list")
@click.argument("collection", shell_complete=_complete_collection)
@click.option("-r", "--recursive", "all_locations", is_flag=True, help="Include all locations (job-postings only)")
@click.option("-q", "--query", metavar="QUERY", help="Filter by company, title, experience level, or URL")
def list_objects(collection, all_locations, query):
    """List objects by collection and exit."""
    from services.application import ApplicationService
    service = ApplicationService()

    if collection == "job-postings" or collection.startswith("job-postings/"):
        if collection == "job-postings":
            location, id_prefix = None, None
        else:
            parts = collection.split("/", 2)
            location = parts[1]
            id_prefix = parts[2] if len(parts) > 2 else None
        results = service.get_job_postings(location=location, all=all_locations, query=query)
        if id_prefix:
            results = [j for j in results if j.get("identifier", "").startswith(id_prefix)]
        for j in results:
            click.echo(f"job-postings/{j.get('identifier', '')}")
    elif collection in ("cvs", "curriculum-vitae"):
        for cv in service.get_cvs(query=query):
            click.echo(f"cvs/{cv.get('identifier', '')}")
    else:
        raise click.UsageError(f"Unknown collection: {collection!r}")


main.add_command(list_objects, name="ls")


def _complete_location(_ctx, _param, incomplete):
    from click.shell_completion import CompletionItem
    candidates = [".", "applied", "archived"]
    return [CompletionItem(c) for c in candidates if c.startswith(incomplete)]


def _require_job_posting_uri(uri: str) -> str:
    try:
        parsed = parse_uri(uri)
    except ValueError:
        raise click.UsageError(f"unrecognised URI '{uri}'\nExpected: job-postings/{{id}}")
    if parsed["collection"] != "job-postings":
        raise click.UsageError(f"unrecognised URI '{uri}'\nExpected: job-postings/{{id}}")
    return parsed["identifier"]


@main.command("transition")
@click.argument("uri", shell_complete=_complete_job_posting_uri)
@click.argument("location", shell_complete=_complete_location)
@click.option("--field", multiple=True, metavar="KEY=VALUE", help="Extra fields to record in the transition log")
def transition(uri, location, field):
    """File a job posting into a named location and exit."""
    from services.application import ApplicationService
    identifier = _require_job_posting_uri(uri)
    if not location:
        raise click.UsageError("location must not be empty")
    if field:
        pairs = [f.split("=", 1) for f in field]
        if any(len(p) < 2 for p in pairs):
            raise click.UsageError("--field values must be KEY=VALUE pairs")
        fields = dict(pairs)
    else:
        fields = None
    ApplicationService().transition_job_posting(identifier, location, fields)
    click.echo(f"Transitioned {uri} to {location!r}")


@main.command("archive")
@click.argument("uri", shell_complete=_complete_job_posting_uri)
def archive(uri):
    """Archive a job posting by URI and exit."""
    identifier = _require_job_posting_uri(uri)
    from services.application import ApplicationService
    ApplicationService().archive_job_posting(identifier)
    click.echo(f"Archived {uri}")


@main.command("unarchive")
@click.argument("uri", shell_complete=_complete_job_posting_uri)
def unarchive(uri):
    """Return an archived job posting to active and exit."""
    identifier = _require_job_posting_uri(uri)
    from services.application import ApplicationService
    ApplicationService().unarchive_job_posting(identifier)
    click.echo(f"Unarchived {uri}")


@main.command("apply")
@click.argument("uri", shell_complete=_complete_job_posting_uri)
@click.argument("cv_identifier", shell_complete=_complete_cv_identifier)
@click.option("--date", metavar="YYYY-MM-DD", help="Application date (defaults to today)")
def apply(uri, cv_identifier, date):
    """Mark a job posting as applied to and exit."""
    identifier = _require_job_posting_uri(uri)
    applied_at = datetime.strptime(date, "%Y-%m-%d") if date else None
    cv_identifier = _normalise_cv_identifier(cv_identifier)
    from services.application import ApplicationService
    ApplicationService().mark_applied(identifier, cv_identifier, applied_at=applied_at)
    click.echo(f"Marked {uri} as applied with {cv_identifier}")


@main.command("add")
@click.argument("uri", shell_complete=_complete_uri)
@click.argument("file", type=click.Path(exists=True))
def add(uri, file):
    """Add a document to an object's directory by URI."""
    from services.application import ApplicationService
    service = ApplicationService()
    try:
        doc_uri = service.add_document(uri, file)
    except ValueError as e:
        raise click.UsageError(str(e))
    click.echo(f"Added {doc_uri}")


def _resolve_content(content: str | None) -> tuple[str | None, bool]:
    """Resolve a content argument to (file_path, is_temp).

    None -> (None, False)    caller fetches from URL
    '-'  -> stdin written to a temp file (is_temp=True)
    else -> (content, False) file path
    """
    if content is None:
        return None, False
    if content == "-":
        data = sys.stdin.buffer.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            tmp.write(data)
            return tmp.name, True
    return content, False


@main.group("analyze")
def analyze():
    """Analyze and save a new object."""


@analyze.command("job-posting")
@click.argument("url")
@click.argument("content", required=False, type=click.Path(dir_okay=False, allow_dash=True))
def analyze_job_posting(url, content):
    """Analyze a job posting.

    URL is required and stored as the posting's identity. Content is fetched from
    the URL unless a file path or '-' (stdin) is given.
    """
    from services.application import ApplicationService
    service = ApplicationService()
    content_file, is_temp = _resolve_content(content)
    try:
        data, identifier, _source_md = service.create_job_posting(url, content_file)
        record = service.save_job_posting(data, identifier)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        if is_temp and content_file:
            os.unlink(content_file)
    click.echo(f"job-postings/{record.identifier}")


@analyze.command("cv")
@click.argument("content", default="-", type=click.Path(dir_okay=False, allow_dash=True))
def analyze_cv(content):
    """Analyze a CV from a file path or stdin (-)."""
    from services.application import ApplicationService
    service = ApplicationService()
    content_file, is_temp = _resolve_content(content)
    try:
        data, identifier = service.create_cv(content_file)
        record = service.save_cv(data, identifier)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        if is_temp and content_file:
            os.unlink(content_file)
    click.echo(f"cvs/{record.identifier}")


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
