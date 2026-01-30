"""
CLI entry point for the Gradio UI.
"""

import argparse
import sys

import yaml


def main():
    """Launch the Gradio UI or show config."""
    parser = argparse.ArgumentParser(description="CV Joint application")
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Print merged configuration to stdout and exit",
    )
    parser.add_argument(
        "--clear-markdown",
        nargs="*",
        metavar=("COLLECTION", "IDENTIFIER"),
        help="Remove generated markdown files and exit. Optional: COLLECTION (job-postings|cvs) and IDENTIFIER",
    )
    args = parser.parse_args()

    if args.show_config:
        from config.settings import get_merged_config

        config = get_merged_config()
        yaml.dump(config, sys.stdout, default_flow_style=False, sort_keys=False)
        return

    if args.clear_markdown is not None:
        from repositories import FileSystemRepository

        repo = FileSystemRepository()
        collection_name = args.clear_markdown[0] if len(args.clear_markdown) > 0 else None
        identifier = args.clear_markdown[1] if len(args.clear_markdown) > 1 else None
        try:
            count = repo.clear_markdown(collection_name, identifier)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Removed {count} markdown file(s)")
        return

    from ui.app import launch

    launch()


if __name__ == "__main__":
    main()
