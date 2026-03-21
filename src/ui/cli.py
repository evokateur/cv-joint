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
    parser.add_argument(
        "--remove",
        metavar="URI",
        help="Remove an object by URI and exit. URI formats: job-postings/{id}, cvs/{id}, job-postings/{id}/cvs/{id}",
    )
    parser.add_argument(
        "--regenerate",
        metavar="URI",
        help="Re-analyze a job posting by URI and overwrite the existing record. URI format: job-postings/{id}",
    )
    parser.add_argument(
        "--content-file",
        metavar="PATH",
        help="Local file to use as content source for --regenerate (instead of fetching the URL)",
    )
    args = parser.parse_args()

    if args.content_file and not args.regenerate:
        parser.error("--content-file requires --regenerate")

    if args.show_config:
        from config.settings import get_merged_config

        config = get_merged_config()
        yaml.dump(config, sys.stdout, default_flow_style=False, sort_keys=False)
        return

    if args.remove is not None:
        from services.application import ApplicationService

        service = ApplicationService()
        uri = args.remove
        parts = uri.strip("/").split("/")

        if parts[0] == "job-postings" and len(parts) == 4 and parts[2] == "cvs":
            removed = service.remove_cv_optimization(parts[1], parts[3])
        elif parts[0] == "job-postings" and len(parts) == 2:
            removed = service.remove_job_posting(parts[1])
        elif parts[0] == "cvs" and len(parts) == 2:
            removed = service.remove_cv(parts[1])
        else:
            print(f"Error: unrecognised URI '{uri}'", file=sys.stderr)
            print(
                "Expected: job-postings/{id}, cvs/{id}, or job-postings/{id}/cvs/{id}",
                file=sys.stderr,
            )
            sys.exit(1)

        if removed:
            print(f"Removed {uri}")
        else:
            print(f"Not found: {uri}", file=sys.stderr)
            sys.exit(1)
        return

    if args.regenerate is not None:
        from services.application import ApplicationService

        service = ApplicationService()
        uri = args.regenerate
        parts = uri.strip("/").split("/")

        if parts[0] == "job-postings" and len(parts) == 2:
            try:
                service.regenerate_job_posting(parts[1], args.content_file)
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
            print(f"Regenerated {uri}")
        else:
            print(f"Error: unrecognised URI '{uri}'", file=sys.stderr)
            print("Expected: job-postings/{id}", file=sys.stderr)
            sys.exit(1)
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
