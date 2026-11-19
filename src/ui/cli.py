import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import click
import yaml
from pydantic import ValidationError

from services.addressing import parse_document_uri, parse_uri, validate_identifier


def _complete_job_posting_uri(ctx, _param, incomplete):
    from click.shell_completion import CompletionItem

    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    return [CompletionItem(c) for c in service.complete_job_posting_uris(incomplete)]


def _complete_cv_identifier(ctx, _param, incomplete):
    """Complete base CVs plus the optimized CVs of the posting in the uri argument."""
    from click.shell_completion import CompletionItem

    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    candidates = service.complete_cv_uris(
        incomplete, job_posting_uri=ctx.params.get("uri")
    )
    return [CompletionItem(c) for c in candidates]


def _complete_base_cv(ctx, _param, incomplete):
    from click.shell_completion import CompletionItem

    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    return [CompletionItem(c) for c in service.complete_cv_uris(incomplete)]


def _normalize_cv_identifier(value: str) -> str:
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


def _complete_export_target(ctx, _param, incomplete):
    from click.shell_completion import CompletionItem
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    return [CompletionItem(c) for c in service.complete_export_targets(incomplete)]


@main.command("export-markdown")
@click.argument("target", required=False, shell_complete=_complete_export_target)
@click.option("-r", "--recursive", is_flag=True)
@click.option("-q", "--query")
@click.pass_context
def export_markdown(ctx, target, recursive, query):
    """Re-export markdown files from stored data and exit."""
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    try:
        count = service.export_markdown(target, recursive=recursive, query=query)
    except (ValueError, FileNotFoundError) as e:
        raise click.UsageError(str(e))
    click.echo(f"Re-exported {count} markdown file(s)")


@main.command("export-schema")
@click.argument("path", required=False, type=click.Path(file_okay=False))
def export_schema(path):
    """Export JSON Schema for domain objects and exit.

    Writes into PATH if given, otherwise into the data directory's schema/ subdirectory.
    """
    from services.schema_export import export_json_schemas

    if path:
        schema_dir = Path(path)
    else:
        from config.root import get_settings

        schema_dir = (
            Path(get_settings().repositories.filesystem.data_dir).expanduser()
            / "schema"
        )

    for written in export_json_schemas(schema_dir):
        click.echo(f"Wrote {written}")


def _complete_render_target(ctx, _param, incomplete):
    from click.shell_completion import CompletionItem
    from renderers.latex import RENDERERS

    typed = ctx.params.get("args") or ()
    if len(typed) == 0:
        # position 1: type literals (cv, cover-letter) + renderable URIs
        from services.application import ApplicationService

        service = ctx.obj if ctx.obj is not None else ApplicationService()
        types = [name for name in RENDERERS if name.startswith(incomplete)]
        candidates = types + service.complete_render_targets(incomplete)
        return [CompletionItem(c) for c in candidates]
    if len(typed) == 1 and typed[0] in RENDERERS:
        # position 2, file mode: stdin sentinel + hand off to shell file globbing
        items = []
        if "-".startswith(incomplete):
            items.append(CompletionItem("-"))
        items.append(CompletionItem(incomplete, type="file"))
        return items
    # URI mode takes no second positional; nothing further to complete
    return []


def _complete_template(ctx, _param, incomplete):
    from click.shell_completion import CompletionItem

    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    return [CompletionItem(n) for n in service.complete_templates(incomplete)]


def _render_target_from_file(doc_type: str, input_path: str):
    """Resolve file mode to (data, type, default base name). INPUT '-' reads stdin."""
    from renderers.latex import load_data

    if input_path == "-":
        return yaml.safe_load(sys.stdin.read()), doc_type, None
    path = Path(input_path)
    if not path.is_file():
        raise click.UsageError(f"no such file: {input_path}")
    return load_data(input_path), doc_type, path.stem


def _render_target_from_uri(uri: str, service=None):
    """Resolve a stored entity to (data, type, default base name)."""
    from models import CoverLetter, CurriculumVitae
    from services.application import ApplicationService

    try:
        parsed = parse_uri(uri)
    except ValueError:
        raise click.UsageError(
            f"unrecognised URI '{uri}'\n"
            "Expected a CV or cover letter URI, "
            "or file mode: render <type> <input>"
        )

    service = service if service is not None else ApplicationService()
    try:
        obj = service.get(uri)
    except (ValueError, OSError) as error:
        raise click.ClickException(str(error)) from error
    if isinstance(obj, CoverLetter):
        doc_type = "cover-letter"
    elif isinstance(obj, CurriculumVitae):
        doc_type = "cv"
    else:
        raise click.UsageError(
            f"not a renderable target: {uri}\nExpected a CV or cover letter URI"
        )
    base_name = parsed["identifier"]
    if parsed["collection"] == "optimized-cvs":
        base_name = f"{parsed['job_posting_identifier']}-{base_name}"
    return obj.model_dump(), doc_type, base_name


def _default_render_filename(base_name: str, fmt: str) -> str:
    ext = "tex" if fmt == "tex" else "pdf"
    return f"{base_name}.{ext}"


def _emit_render(data, doc_type, fmt, output, default_base_name, template):
    """Render `data` and write it per the -o convention (path, '-' stdout, or CWD)."""
    from renderers.latex import render_document

    ext = "tex" if fmt == "tex" else "pdf"
    try:
        if output == "-":
            with tempfile.TemporaryDirectory() as tmp:
                tmp_out = str(Path(tmp) / f"artifact.{ext}")
                render_document(
                    data, doc_type, fmt=fmt, output_path=tmp_out, template=template
                )
                sys.stdout.buffer.write(Path(tmp_out).read_bytes())
        else:
            if output:
                dest = output
            elif default_base_name:
                dest = _default_render_filename(default_base_name, fmt)
            else:
                raise click.UsageError(
                    "reading from stdin (-) requires -o <path> or -o -"
                )
            path = render_document(
                data, doc_type, fmt=fmt, output_path=dest, template=template
            )
            click.echo(f"Wrote {path}", err=True)
    except ValueError as e:
        raise click.ClickException(str(e))


@main.command("render")
@click.argument(
    "args",
    nargs=-1,
    required=True,
    metavar="TARGET [INPUT]",
    shell_complete=_complete_render_target,
)
@click.option(
    "-f",
    "--format",
    "fmt",
    type=click.Choice(["pdf", "tex"]),
    default="pdf",
    show_default=True,
    help="Output format.",
)
@click.option(
    "-o",
    "--output",
    metavar="PATH",
    help="Output path, or '-' for stdout. Default: current directory.",
)
@click.option(
    "--template",
    metavar="NAME",
    help="Override the type's default template.",
    shell_complete=_complete_template,
)
@click.pass_context
def render(ctx, args, fmt, output, template):
    """Render a document to PDF or TeX.

    \b
    cv-joint render <uri>            a stored CV or cover letter
    cv-joint render <type> <input>   a data file or '-' (stdin), e.g. cv data/cv.yaml
    """
    if len(args) == 1:
        data, doc_type, base_name = _render_target_from_uri(args[0], ctx.obj)
    elif len(args) == 2:
        data, doc_type, base_name = _render_target_from_file(args[0], args[1])
    else:
        raise click.UsageError("render takes <uri> or <type> <input>")
    _emit_render(data, doc_type, fmt, output, base_name, template)


def _complete_target(ctx, _param, incomplete):
    from click.shell_completion import CompletionItem
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    return [CompletionItem(uri) for uri in service.complete_targets(incomplete)]


@main.command("remove")
@click.argument("uri", shell_complete=_complete_target)
@click.pass_context
def remove(ctx, uri):
    """Remove an entity or document and print its URI."""
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    try:
        if parse_document_uri(uri) is not None:
            affected_uri = service.remove_document(uri)
        else:
            affected_uri = service.remove(uri)
    except (ValueError, OSError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(affected_uri)


def _strip_uri_prefix(old_uri: str, old_identifier: str, new_value: str) -> str:
    """Strip old_uri's container prefix from new_value when it carries it.

    Lets shell completion fill in a full URI (e.g. cvs/bar) while rename reads
    the trailing segment as the new identifier. Extraction only, no validation.
    """
    prefix = old_uri.strip("/")[: -len(old_identifier)]
    return new_value[len(prefix) :] if new_value.startswith(prefix) else new_value


@main.command("rename")
@click.argument("uri", shell_complete=_complete_target)
@click.argument("new_name")
@click.pass_context
def rename(ctx, uri, new_name):
    """Rename an entity or document and print its new URI."""
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    try:
        if parse_document_uri(uri) is not None:
            affected_uri = service.rename_document(uri, new_name)
        else:
            parsed = parse_uri(uri)
            new_identifier = _strip_uri_prefix(uri, parsed["identifier"], new_name)
            affected_uri = service.rename(uri, new_identifier)
    except (ValueError, OSError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(affected_uri)


def _complete_add_destination(ctx, _param, incomplete):
    from click.shell_completion import CompletionItem
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    return [
        CompletionItem(uri) for uri in service.complete_add_destinations(incomplete)
    ]


def _complete_load_destination(ctx, _param, incomplete):
    from click.shell_completion import CompletionItem
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    return [
        CompletionItem(uri) for uri in service.complete_load_destinations(incomplete)
    ]


@main.command("list")
@click.argument("uri", shell_complete=_complete_target)
@click.option(
    "-r",
    "--recursive",
    is_flag=True,
    help="Select records across every location",
)
@click.option(
    "-q",
    "--query",
    metavar="QUERY",
    help="Match a case-insensitive substring of the whole record",
)
@click.pass_context
def list_objects(ctx, uri, recursive, query):
    """Print canonical URIs for selected records or an entity's children."""
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    try:
        uris = service.list(uri, recursive=recursive, query=query)
    except (ValueError, OSError) as error:
        raise click.ClickException(str(error)) from error
    for uri in uris:
        click.echo(uri)


main.add_command(list_objects, name="ls")


@main.command("get")
@click.argument("uri", shell_complete=_complete_target)
@click.option(
    "-r", "--recursive", is_flag=True, help="Select records across every location"
)
@click.option(
    "-q", "--query", help="Match a case-insensitive substring of the whole record"
)
@click.pass_context
def get_content(ctx, uri, recursive, query):
    """Print entity JSON, selected records as JSONL, or raw document bytes."""
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    try:
        if parse_document_uri(uri) is not None:
            click.get_binary_stream("stdout").write(service.get_document(uri))
            return
        result = service.get(uri, recursive=recursive, query=query)
    except (ValueError, OSError) as error:
        raise click.ClickException(str(error)) from error
    if isinstance(result, list):
        for record in result:
            click.echo(record.model_dump_json())
    else:
        click.echo(result.model_dump_json())


def _complete_location(_ctx, _param, incomplete):
    from click.shell_completion import CompletionItem

    candidates = [".", "applied", "archived"]
    return [CompletionItem(c) for c in candidates if c.startswith(incomplete)]


def _require_job_posting_uri(uri: str) -> str:
    try:
        parsed = parse_uri(uri)
    except ValueError:
        raise click.UsageError(
            f"unrecognised URI '{uri}'\nExpected: job-postings/{{id}}"
        )
    if parsed["collection"] != "job-postings":
        raise click.UsageError(
            f"unrecognised URI '{uri}'\nExpected: job-postings/{{id}}"
        )
    return parsed["identifier"]


@main.command("transition")
@click.argument("uri", shell_complete=_complete_job_posting_uri)
@click.argument("location", shell_complete=_complete_location)
@click.option(
    "--field",
    multiple=True,
    metavar="KEY=VALUE",
    help="Extra fields to record in the transition log",
)
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
    try:
        ApplicationService().transition_job_posting(identifier, location, fields)
    except ValueError as e:
        raise click.UsageError(str(e))
    click.echo(f"Transitioned {uri} to {location!r}")


@main.command("archive")
@click.argument("uri", shell_complete=_complete_job_posting_uri)
def archive(uri):
    """Archive a job posting by URI and exit."""
    identifier = _require_job_posting_uri(uri)
    from services.application import ApplicationService

    try:
        ApplicationService().archive_job_posting(identifier)
    except ValueError as e:
        raise click.UsageError(str(e))
    click.echo(f"Archived {uri}")


@main.command("unarchive")
@click.argument("uri", shell_complete=_complete_job_posting_uri)
def unarchive(uri):
    """Return an archived job posting to active and exit."""
    identifier = _require_job_posting_uri(uri)
    from services.application import ApplicationService

    try:
        ApplicationService().unarchive_job_posting(identifier)
    except ValueError as e:
        raise click.UsageError(str(e))
    click.echo(f"Unarchived {uri}")


@main.command("apply")
@click.argument("uri", shell_complete=_complete_job_posting_uri)
@click.argument("cv_identifier", shell_complete=_complete_cv_identifier)
@click.option(
    "--date", metavar="YYYY-MM-DD", help="Application date (defaults to today)"
)
@click.pass_context
def apply(ctx, uri, cv_identifier, date):
    """Mark a job posting as applied to and exit."""
    identifier = _require_job_posting_uri(uri)
    applied_at = datetime.strptime(date, "%Y-%m-%d") if date else None
    cv_identifier = _normalize_cv_identifier(cv_identifier)
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    try:
        service.mark_applied(identifier, cv_identifier, applied_at=applied_at)
    except ValueError as e:
        raise click.UsageError(str(e))
    click.echo(f"Marked {uri} as applied with {cv_identifier}")


def _validation_summary(error: ValidationError) -> str:
    details = error.errors(include_url=False, include_input=False)
    first = details[0]
    field = ".".join(str(part) for part in first["loc"])
    remaining = f" (and {len(details) - 1} more)" if len(details) > 1 else ""
    return f"Invalid entity content: {field}: {first['msg']}{remaining}"


@main.command("update")
@click.argument("uri", shell_complete=_complete_target)
@click.argument("file", type=click.Path(exists=True, dir_okay=False, allow_dash=True))
@click.pass_context
def update(ctx, uri, file):
    """Replace an entity's content or a document's bytes."""
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    try:
        with click.open_file(file, "rb") as source:
            content = source.read()
        if parse_document_uri(uri) is not None:
            affected_uri = service.update_document(uri, content)
        else:
            affected_uri = service.update(uri, content.decode())
    except ValidationError as error:
        raise click.ClickException(_validation_summary(error)) from error
    except (ValueError, OSError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(affected_uri)


@main.command("add")
@click.argument("uri", shell_complete=_complete_add_destination)
@click.argument("file", type=click.Path(exists=True, dir_okay=False, allow_dash=True))
@click.pass_context
def add(ctx, uri, file):
    """Create the entity or document at URI, or attach FILE under ENTITY/."""
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    with click.open_file(file, "rb") as source:
        content = source.read()
    try:
        if uri.endswith("/"):
            if file == "-":
                raise click.UsageError("stdin needs a document URI for its filename")
            affected_uri = service.add_document(f"{uri}{Path(file).name}", content)
        elif parse_document_uri(uri) is not None:
            affected_uri = service.add_document(uri, content)
        else:
            affected_uri = service.add(uri, content.decode())
    except ValidationError as error:
        raise click.ClickException(_validation_summary(error)) from error
    except (ValueError, OSError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(affected_uri)


@main.group("analyze")
def analyze():
    """Analyze external content into named outputs, without saving anything."""


def _analyze_posting(service, source, url):
    """Analyze posting input, reporting an unreadable file as a CLI error."""
    if source.startswith(("https://", "http://")):
        return service.analyze_job_posting_url(source, url=url)
    try:
        with click.open_file(source) as content:
            text = content.read()
    except OSError as error:
        raise click.ClickException(str(error)) from error
    return service.analyze_job_posting(text, url=url)


@analyze.command("job-posting")
@click.argument("source", default="-")
@click.option("--url", help="Posting URL to store; overrides a URL source")
@click.pass_context
def analyze_job_posting(ctx, source, url):
    """Analyze a posting from a URL, file or stdin into named outputs."""
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    click.echo(json.dumps(_analyze_posting(service, source, url), indent=2))


@analyze.command("cv")
@click.argument(
    "file", default="-", type=click.Path(exists=True, dir_okay=False, allow_dash=True)
)
@click.pass_context
def analyze_cv(ctx, file):
    """Analyze a CV from a file or stdin (-) and print its named outputs."""
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    with click.open_file(file) as source:
        content = source.read()
    click.echo(json.dumps(service.analyze_cv(content), indent=2))


def _existing_entity(collection: str, kind: str):
    """Click callback requiring the URI of an existing entity in collection."""

    def callback(ctx, _param, uri):
        from services.application import ApplicationService

        if ctx.obj is None:
            ctx.obj = ApplicationService()
        try:
            parsed = parse_uri(uri)
        except ValueError:
            parsed = {}
        if parsed.get("collection") != collection or not ctx.obj.object_exists(uri):
            raise click.BadParameter(f"not an existing {kind}: {uri}")
        return uri

    return callback


@main.command("optimize")
@click.argument(
    "cv_uri",
    callback=_existing_entity("cvs", "base CV"),
    shell_complete=_complete_base_cv,
)
@click.argument(
    "job_posting_uri",
    callback=_existing_entity("job-postings", "job posting"),
    shell_complete=_complete_job_posting_uri,
)
@click.pass_context
def optimize(ctx, cv_uri, job_posting_uri):
    """Optimize a base CV for a job posting and print its named outputs."""
    outputs = ctx.obj.optimize(cv_uri, job_posting_uri)
    click.echo(json.dumps(outputs, indent=2))


@main.command("load")
@click.argument("uri", shell_complete=_complete_load_destination)
@click.pass_context
def load(ctx, uri):
    """Create exactly the entity at URI from named outputs on stdin."""
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    outputs = click.get_text_stream("stdin").read()
    click.echo(_load(service, uri, outputs))


def _load(service, uri: str, outputs) -> str:
    """Load named outputs, reporting failures as CLI errors."""
    try:
        return service.load(uri, outputs)
    except ValidationError as error:
        raise click.ClickException(_validation_summary(error)) from error
    except (ValueError, OSError) as error:
        raise click.ClickException(str(error)) from error


@main.group("ingest")
def ingest():
    """Analyze external content and persist it as a new object."""


def _ingest(service, collection: str, identifier: str | None, analyze) -> str:
    """Analyze and load into collection, at identifier or a generated free URI.

    An explicit identifier is validated before any analysis runs.
    """
    from services.application import PRODUCER_OUTPUT_PRIMARY_FILES

    if identifier is not None:
        try:
            validate_identifier(identifier)
        except ValueError as error:
            raise click.ClickException(str(error)) from error
    outputs = analyze()
    if identifier is None:
        entity_uri = service.generate_default_entity_uri(
            collection, outputs[PRODUCER_OUTPUT_PRIMARY_FILES[collection]]
        )
    else:
        entity_uri = f"{collection}/{identifier}"
    return _load(service, entity_uri, outputs)


@ingest.command("job-posting")
@click.argument("source", default="-")
@click.option("--url", help="Posting URL to store; overrides a URL source")
@click.option("-i", "--identifier", help="Identifier for the new posting")
@click.pass_context
def ingest_job_posting(ctx, source, url, identifier):
    """Analyze a posting from a URL, file or stdin and load it."""
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    click.echo(
        _ingest(
            service,
            "job-postings",
            identifier,
            lambda: _analyze_posting(service, source, url),
        )
    )


@ingest.command("cv")
@click.argument(
    "file", default="-", type=click.Path(exists=True, dir_okay=False, allow_dash=True)
)
@click.option("-i", "--identifier", help="Identifier for the new CV")
@click.pass_context
def ingest_cv(ctx, file, identifier):
    """Analyze a CV from a file or stdin (-) and load it into cvs."""
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()

    def analyze_file():
        with click.open_file(file) as source:
            return service.analyze_cv(source.read())

    click.echo(_ingest(service, "cvs", identifier, analyze_file))


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
