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
        "--regenerate-markdown",
        nargs="?",
        const="all",
        metavar="COLLECTION",
        help="Regenerate markdown files from stored data and exit. Optional: COLLECTION (job-postings|cvs)",
    )
    args = parser.parse_args()

    if args.show_config:
        from config.settings import get_merged_config

        config = get_merged_config()
        yaml.dump(config, sys.stdout, default_flow_style=False, sort_keys=False)
        return

    if args.regenerate_markdown is not None:
        from services.application import ApplicationService

        service = ApplicationService()
        collection_name = None if args.regenerate_markdown == "all" else args.regenerate_markdown
        try:
            count = service.regenerate_markdown(collection_name)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Regenerated {count} markdown file(s)")
        return

    from ui.app import launch

    launch()


if __name__ == "__main__":
    main()
