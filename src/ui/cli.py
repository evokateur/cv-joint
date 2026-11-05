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
        [
            f"job-postings/{item['identifier']}"
            for item in _load_collection("job-postings")
        ]
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

    candidates = [
        f"job-postings/{item['identifier']}"
        for item in _load_collection("job-postings")
    ]
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
                if item.get("job_posting_identifier") == jp_id
                and item.get("identifier")
            ]
    except ValueError:
        pass
    candidates += [f"cvs/{item['identifier']}" for item in _load_collection("cvs")]
    return [CompletionItem(c) for c in candidates if c.startswith(incomplete)]


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


def _renderable_uris() -> list[str]:
    """URIs that resolve to a CV (the only renderable targets today).

    Never a bare job-postings/{id} — that is not a CV, so it is pruned; only its
    cvs/{id} leaves are offered. Invariant: if it completes, it renders.
    """
    uris = [f"cvs/{item['identifier']}" for item in _load_collection("cvs")]
    uris += [
        f"job-postings/{item['job_posting_identifier']}/cvs/{item['identifier']}"
        for item in _load_collection("optimized-cvs")
        if item.get("job_posting_identifier") and item.get("identifier")
    ]
    return uris


def _complete_render_target(ctx, _param, incomplete):
    from click.shell_completion import CompletionItem
    from renderers.latex import RENDERERS

    typed = ctx.params.get("args") or ()
    if len(typed) == 0:
        # position 1: type literals (cv, cover-letter) + renderable URIs
        candidates = list(RENDERERS) + _renderable_uris()
        return [CompletionItem(c) for c in candidates if c.startswith(incomplete)]
    if len(typed) == 1 and typed[0] in RENDERERS:
        # position 2, file mode: stdin sentinel + hand off to shell file globbing
        items = []
        if "-".startswith(incomplete):
            items.append(CompletionItem("-"))
        items.append(CompletionItem(incomplete, type="file"))
        return items
    # URI mode takes no second positional; nothing further to complete
    return []


def _complete_template(_ctx, _param, incomplete):
    from click.shell_completion import CompletionItem

    templates_dir = Path(__file__).parents[2] / "templates"
    names = sorted(p.name for p in templates_dir.glob("*.tex"))
    return [CompletionItem(n) for n in names if n.startswith(incomplete)]


def _render_target_from_file(doc_type: str, input_path: str):
    """Resolve file mode to (data, type, default base name). INPUT '-' reads stdin."""
    from renderers.latex import load_data

    if input_path == "-":
        return yaml.safe_load(sys.stdin.read()), doc_type, None
    path = Path(input_path)
    if not path.is_file():
        raise click.UsageError(f"no such file: {input_path}")
    return load_data(input_path), doc_type, path.stem


def _render_target_from_uri(uri: str):
    """Resolve a stored CV URI to (data, type, default base name)."""
    from services.application import ApplicationService

    try:
        parsed = parse_uri(uri)
    except ValueError:
        raise click.UsageError(
            f"unrecognised URI '{uri}'\n"
            "Expected a CV (cvs/{{id}} or job-postings/{{id}}/cvs/{{id}}), "
            "or file mode: render <type> <input>"
        )

    service = ApplicationService()
    if parsed["collection"] == "cvs":
        obj = service.get_cv(parsed["identifier"])
        base_name = parsed["identifier"]
    elif parsed["collection"] == "optimized-cvs":
        obj = service.get_optimized_cv(
            parsed["job_posting_identifier"], parsed["identifier"]
        )
        base_name = f"{parsed['job_posting_identifier']}-{parsed['identifier']}"
    else:
        raise click.UsageError(
            f"not a renderable CV target: {uri}\n"
            "Expected cvs/{{id}} or job-postings/{{id}}/cvs/{{id}}"
        )

    if obj is None:
        click.echo(f"Not found: {uri}", err=True)
        sys.exit(1)
    return obj.model_dump(), "cv", base_name


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
def render(args, fmt, output, template):
    """Render a document to PDF or TeX.

    \b
    cv-joint render <uri>            a stored CV, e.g. cvs/my-cv
    cv-joint render <type> <input>   a data file or '-' (stdin), e.g. cv data/cv.yaml
    """
    if len(args) == 1:
        data, doc_type, base_name = _render_target_from_uri(args[0])
    elif len(args) == 2:
        data, doc_type, base_name = _render_target_from_file(args[0], args[1])
    else:
        raise click.UsageError("render takes <uri> or <type> <input>")
    _emit_render(data, doc_type, fmt, output, base_name, template)


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
        removed = service.remove_optimized_cv(
            parsed["job_posting_identifier"], parsed["identifier"]
        )
    elif parsed["collection"] == "job-postings":
        removed = service.remove_job_posting(parsed["identifier"])
    elif parsed["collection"] == "cvs":
        removed = service.remove_cv(parsed["identifier"])
    else:
        raise click.UsageError(f"remove is not implemented for {parsed['collection']}")

    if removed:
        click.echo(f"Removed {uri}")
    else:
        click.echo(f"Not found: {uri}", err=True)
        sys.exit(1)


def _strip_uri_prefix(old_uri: str, old_identifier: str, new_value: str) -> str:
    """Strip old_uri's container prefix from new_value when it carries it.

    Lets shell completion fill in a full URI (e.g. cvs/bar) while rename reads
    the trailing segment as the new identifier. Extraction only, no validation.
    """
    prefix = old_uri.strip("/")[: -len(old_identifier)]
    return new_value[len(prefix) :] if new_value.startswith(prefix) else new_value


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

    new_id = _strip_uri_prefix(uri, parsed["identifier"], new_id)
    try:
        validate_identifier(new_id)
    except ValueError:
        raise click.UsageError(
            f"illegal new identifier '{new_id}'\n"
            "Expected a bare identifier (no '/' or spaces), optionally prefixed with the source collection"
        )

    try:
        if parsed["collection"] == "job-postings":
            service.rename_job_posting(parsed["identifier"], new_id)
        elif parsed["collection"] == "cvs":
            service.rename_cv(parsed["identifier"], new_id)
        elif parsed["collection"] == "optimized-cvs":
            service.rename_optimized_cv(
                parsed["job_posting_identifier"], parsed["identifier"], new_id
            )
        else:
            raise click.UsageError(
                f"rename is not implemented for {parsed['collection']}"
            )
    except click.UsageError:
        raise
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Renamed {uri} to {new_id}")


def _complete_target(ctx, _param, incomplete):
    from click.shell_completion import CompletionItem
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    return [CompletionItem(uri) for uri in service.complete_targets(incomplete)]


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
def apply(uri, cv_identifier, date):
    """Mark a job posting as applied to and exit."""
    identifier = _require_job_posting_uri(uri)
    applied_at = datetime.strptime(date, "%Y-%m-%d") if date else None
    cv_identifier = _normalize_cv_identifier(cv_identifier)
    from services.application import ApplicationService

    try:
        ApplicationService().mark_applied(
            identifier, cv_identifier, applied_at=applied_at
        )
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
    """Read posting input and report input or analysis failures as CLI errors."""
    try:
        if source.startswith(("https://", "http://")):
            return service.analyze_job_posting_url(source)
        with click.open_file(source) as content:
            return service.analyze_job_posting(content.read(), url=url)
    except (ValueError, OSError) as error:
        raise click.ClickException(str(error)) from error


@analyze.command("job-posting")
@click.argument("source", default="-")
@click.option("--url", help="Posting URL for file or stdin input")
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


@ingest.command("job-posting")
@click.argument("source", default="-")
@click.option("--url", help="Posting URL for file or stdin input")
@click.option("-i", "--identifier", help="Identifier for the new posting")
@click.pass_context
def ingest_job_posting(ctx, source, url, identifier):
    """Analyze a posting from a URL, file or stdin and load it."""
    from services.application import ApplicationService

    service = ctx.obj if ctx.obj is not None else ApplicationService()
    if identifier is not None:
        try:
            validate_identifier(identifier)
        except ValueError as error:
            raise click.ClickException(str(error)) from error
    outputs = _analyze_posting(service, source, url)
    if identifier is None:
        entity_uri = service.generate_default_entity_uri(
            "job-postings", outputs["job-posting.json"]
        )
    else:
        entity_uri = f"job-postings/{identifier}"
    click.echo(_load(service, entity_uri, outputs))


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
    if identifier is not None:
        try:
            validate_identifier(identifier)
        except ValueError as error:
            raise click.ClickException(str(error)) from error
    with click.open_file(file) as source:
        content = source.read()
    outputs = service.analyze_cv(content)
    if identifier is None:
        entity_uri = service.generate_default_entity_uri(
            "cvs", outputs["curriculum-vitae.json"]
        )
    else:
        entity_uri = f"cvs/{identifier}"
    click.echo(_load(service, entity_uri, outputs))


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
