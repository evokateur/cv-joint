import argparse
import stat
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from .extractor import select_extractor


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="extract-post",
        description="Extract a job posting from an HTML file or URL as Markdown.",
    )
    parser.add_argument(
        "input",
        help="Path to the saved HTML file or an http/https URL",
    )
    parser.add_argument(
        "output",
        nargs="?",
        help="Optional path for the generated Markdown file",
    )
    return parser.parse_args(argv)


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _fetch_url_html(url: str) -> str:
    with urlopen(url) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset)


def _build_output_path(input_value: str) -> Path:
    if not _is_url(input_value):
        return Path(input_value).with_suffix(".md")

    parsed = urlparse(input_value)
    slug = Path(parsed.path).name or parsed.netloc or "posting"
    return Path(f"{slug}.md")


def _stdout_is_pipe() -> bool:
    return stat.S_ISFIFO(Path("/dev/stdout").stat().st_mode)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    write_to_stdout = not args.output and _stdout_is_pipe()
    status_stream = sys.stderr if write_to_stdout else sys.stdout

    try:
        if _is_url(args.input):
            html = _fetch_url_html(args.input)
            extractor = select_extractor(html, source_url=args.input)
            print(f"Using {extractor.__name__}...", file=status_stream)
            job = extractor.from_string(html, source_url=args.input).extract()
        else:
            input_file = Path(args.input)
            if not input_file.exists():
                print(f"Error: file not found: {input_file}", file=sys.stderr)
                return 1
            html = input_file.read_text(encoding="utf-8")
            extractor = select_extractor(html)
            print(f"Using {extractor.__name__}...", file=status_stream)
            job = extractor.from_string(html).extract()
    except (OSError, ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    markdown = job.to_markdown()
    if write_to_stdout:
        print(markdown, end="")
        return 0

    output_file = Path(args.output) if args.output else _build_output_path(args.input)
    output_file.write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
