"""User-specified identifier CLI machinery."""

from collections.abc import Callable

import click


def validate_identifier(value: str) -> str:
    """Return value unchanged, or raise if it is empty, has whitespace, or a '/'."""
    if not value or "/" in value or any(c.isspace() for c in value):
        raise click.UsageError(
            f"illegal identifier {value!r}: must be non-empty with no spaces or '/'"
        )
    return value


def identifier_option(f):
    """Add the shared -i/--identifier option to a command."""
    return click.option(
        "-i",
        "--identifier",
        "identifier",
        default=None,
        help="Identifier for the new object. Prompted for if omitted.",
    )(f)


def resolve_identifier(
    given: str | None,
    default: str | None,
    exists: Callable[[str], bool],
    *,
    interactive: bool,
) -> str:
    """Resolve the identifier to persist under.

    given not None -> validate and reject on invalid or collision.
    given None, interactive -> prompt with default, re-prompt on invalid or collision.
    given None, non-interactive -> require --identifier.
    """
    if given is not None:
        validate_identifier(given)
        if exists(given):
            raise click.UsageError(f'identifier "{given}" already exists')
        return given

    if not interactive:
        raise click.UsageError("--identifier is required in non-interactive use")

    def check(value: str) -> str:
        validate_identifier(value)
        if exists(value):
            raise click.UsageError(f'identifier "{value}" is taken')
        return value

    return click.prompt("Identifier", default=default, value_proc=check)
