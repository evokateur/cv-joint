import sys
from datetime import datetime

import click
import yaml


def _normalise_cv_identifier(value: str) -> str:
    parts = value.strip("/").split("/")
    if parts[0] == "job-postings" and len(parts) == 4 and parts[2] == "cvs":
        return f"{parts[1]}/{parts[3]}"
    if parts[0] == "cvs" and len(parts) == 2:
        return parts[1]
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


@main.command("regenerate-markdown")
@click.argument("collection", required=False)
def regenerate_markdown(collection):
    """Regenerate markdown files from stored data and exit."""
    from services.application import ApplicationService
    service = ApplicationService()
    try:
        count = service.regenerate_markdown(collection)
    except ValueError as e:
        raise click.UsageError(str(e))
    click.echo(f"Regenerated {count} markdown file(s)")


@main.command("remove")
@click.argument("uri")
def remove(uri):
    """Remove an object by URI and exit."""
    from services.application import ApplicationService
    service = ApplicationService()
    parts = uri.strip("/").split("/")

    if parts[0] == "job-postings" and len(parts) == 4 and parts[2] == "cvs":
        removed = service.remove_cv_optimization(parts[1], parts[3])
    elif parts[0] == "job-postings" and len(parts) == 2:
        removed = service.remove_job_posting(parts[1])
    elif parts[0] == "cvs" and len(parts) == 2:
        removed = service.remove_cv(parts[1])
    else:
        raise click.UsageError(
            f"unrecognised URI '{uri}'\n"
            "Expected: job-postings/{{id}}, cvs/{{id}}, or job-postings/{{id}}/cvs/{{id}}"
        )

    if removed:
        click.echo(f"Removed {uri}")
    else:
        click.echo(f"Not found: {uri}", err=True)
        sys.exit(1)


@main.command("regenerate")
@click.argument("uri")
@click.argument("content_file", required=False)
def regenerate(uri, content_file):
    """Re-analyze an object by URI and overwrite the existing record."""
    from services.application import ApplicationService
    service = ApplicationService()
    parts = uri.strip("/").split("/")

    try:
        if parts[0] == "job-postings" and len(parts) == 2:
            service.regenerate_job_posting(parts[1], content_file)
        elif parts[0] == "cvs" and len(parts) == 2:
            if not content_file:
                raise click.UsageError("regenerate cvs/{id} requires CONTENT_FILE")
            service.regenerate_cv(parts[1], content_file)
        elif parts[0] == "job-postings" and len(parts) == 4 and parts[2] == "cvs":
            service.regenerate_cv_optimization(parts[1], parts[3])
        else:
            raise click.UsageError(
                f"unrecognised URI '{uri}'\n"
                "Expected: job-postings/{{id}}, cvs/{{id}}, or job-postings/{{id}}/cvs/{{id}}"
            )
    except click.UsageError:
        raise
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Regenerated {uri}")


@main.command("rename")
@click.argument("uri")
@click.argument("new_id")
def rename(uri, new_id):
    """Rename an object by URI and exit."""
    from services.application import ApplicationService
    service = ApplicationService()
    parts = uri.strip("/").split("/")

    try:
        if parts[0] == "job-postings" and len(parts) == 2:
            service.rename_job_posting(parts[1], new_id)
        elif parts[0] == "cvs" and len(parts) == 2:
            service.rename_cv(parts[1], new_id)
        elif parts[0] == "job-postings" and len(parts) == 4 and parts[2] == "cvs":
            service.rename_cv_optimization(parts[1], parts[3], new_id)
        else:
            raise click.UsageError(
                f"unrecognised URI '{uri}'\n"
                "Expected: job-postings/{{id}}, cvs/{{id}}, or job-postings/{{id}}/cvs/{{id}}"
            )
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
        for cv in service.get_cvs():
            click.echo(f"cvs/{cv.get('identifier', '')}")


@main.command("archive")
@click.argument("uri")
def archive(uri):
    """Archive a job posting by URI and exit."""
    from services.application import ApplicationService
    service = ApplicationService()
    parts = uri.strip("/").split("/")

    if parts[0] == "job-postings" and len(parts) == 2:
        service.archive_job_posting(parts[1])
        click.echo(f"Archived {uri}")
    else:
        raise click.UsageError(
            f"unrecognised URI '{uri}'\nExpected: job-postings/{{id}}"
        )


@main.command("apply")
@click.argument("uri")
@click.argument("cv_identifier")
@click.option("--date", metavar="YYYY-MM-DD", help="Application date (defaults to today)")
def apply(uri, cv_identifier, date):
    """Mark a job posting as applied to and exit."""
    from services.application import ApplicationService
    service = ApplicationService()
    parts = uri.strip("/").split("/")

    if parts[0] == "job-postings" and len(parts) == 2:
        applied_at = datetime.strptime(date, "%Y-%m-%d") if date else None
        cv_identifier = _normalise_cv_identifier(cv_identifier)
        service.mark_applied(parts[1], cv_identifier, applied_at=applied_at)
        click.echo(f"Marked {uri} as applied with {cv_identifier}")
    else:
        raise click.UsageError(
            f"unrecognised URI '{uri}'\nExpected: job-postings/{{id}}"
        )


if __name__ == "__main__":
    main()
