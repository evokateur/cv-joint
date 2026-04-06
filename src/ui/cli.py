"""
CLI entry point for the Gradio UI.
"""

import sys

import yaml


def main():
    """Launch the Gradio UI or run a management command."""
    import argparse

    parser = argparse.ArgumentParser(description="CV Joint application")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("launch", help="Start the Gradio server")
    subparsers.add_parser("open", help="Start the Gradio server and open it in a browser")
    subparsers.add_parser("show-config", help="Print merged configuration to stdout and exit")

    regen_md = subparsers.add_parser(
        "regenerate-markdown",
        help="Regenerate markdown files from stored data and exit",
    )
    regen_md.add_argument(
        "collection",
        nargs="?",
        metavar="COLLECTION",
        help="Collection to regenerate (job-postings|cvs|optimizations); omit for all",
    )

    remove_cmd = subparsers.add_parser("remove", help="Remove an object by URI and exit")
    remove_cmd.add_argument(
        "uri",
        metavar="URI",
        help="URI formats: job-postings/{id}, cvs/{id}, job-postings/{id}/cvs/{id}",
    )

    regen_cmd = subparsers.add_parser(
        "regenerate",
        help="Re-analyze an object by URI and overwrite the existing record",
    )
    regen_cmd.add_argument(
        "uri",
        metavar="URI",
        help="URI formats: job-postings/{id}, cvs/{id}, job-postings/{id}/cvs/{id}",
    )
    regen_cmd.add_argument(
        "content_file",
        nargs="?",
        metavar="CONTENT_FILE",
        help="Local file to use as content source (required for cvs/{id})",
    )

    rename_cmd = subparsers.add_parser("rename", help="Rename an object by URI and exit")
    rename_cmd.add_argument("uri", metavar="URI")
    rename_cmd.add_argument("new_id", metavar="NEW_ID")

    list_cmd = subparsers.add_parser("list", help="List objects by collection and exit")
    list_cmd.add_argument(
        "collection",
        metavar="COLLECTION",
        choices=["job-postings"],
        help="Collection to list (job-postings)",
    )
    list_cmd.add_argument(
        "--archived",
        action="store_true",
        help="Show only archived entries",
    )

    archive_cmd = subparsers.add_parser(
        "archive", help="Archive a job posting by URI and exit"
    )
    archive_cmd.add_argument(
        "uri",
        metavar="URI",
        help="URI format: job-postings/{id}",
    )

    apply_cmd = subparsers.add_parser(
        "apply", help="Mark a job posting as applied to and exit"
    )
    apply_cmd.add_argument(
        "uri",
        metavar="URI",
        help="URI format: job-postings/{id}",
    )
    apply_cmd.add_argument("cv_identifier", metavar="CV_IDENTIFIER")
    apply_cmd.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="Application date (defaults to today)",
    )

    args = parser.parse_args()

    if args.command is None or args.command == "launch":
        from ui.app import launch
        launch(inbrowser=False)
        return

    if args.command == "open":
        from ui.app import launch
        launch(inbrowser=True)
        return

    if args.command == "show-config":
        from config.settings import get_merged_config
        config = get_merged_config()
        yaml.dump(config, sys.stdout, default_flow_style=False, sort_keys=False)
        return

    if args.command == "regenerate-markdown":
        from services.application import ApplicationService
        service = ApplicationService()
        try:
            count = service.regenerate_markdown(args.collection)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Regenerated {count} markdown file(s)")
        return

    if args.command == "remove":
        from services.application import ApplicationService
        service = ApplicationService()
        uri = args.uri
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

    if args.command == "regenerate":
        from services.application import ApplicationService
        service = ApplicationService()
        uri = args.uri
        parts = uri.strip("/").split("/")

        try:
            if parts[0] == "job-postings" and len(parts) == 2:
                service.regenerate_job_posting(parts[1], args.content_file)
            elif parts[0] == "cvs" and len(parts) == 2:
                if not args.content_file:
                    parser.error("regenerate cvs/{id} requires CONTENT_FILE")
                service.regenerate_cv(parts[1], args.content_file)
            elif parts[0] == "job-postings" and len(parts) == 4 and parts[2] == "cvs":
                service.regenerate_cv_optimization(parts[1], parts[3])
            else:
                print(f"Error: unrecognised URI '{uri}'", file=sys.stderr)
                print(
                    "Expected: job-postings/{id}, cvs/{id}, or job-postings/{id}/cvs/{id}",
                    file=sys.stderr,
                )
                sys.exit(1)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Regenerated {uri}")
        return

    if args.command == "list":
        from services.application import ApplicationService
        service = ApplicationService()

        if args.collection == "job-postings":
            if args.archived:
                jobs = [j for j in service.get_job_postings(archived=True) if j.get("is_archived")]
            else:
                jobs = service.get_job_postings(archived=False)
            for j in jobs:
                date = (j.get("created_at") or "")[:10]
                print(f"{date}  {j.get('company', ''):<25} {j.get('title', ''):<30} {j.get('identifier', '')}")
        return

    if args.command == "archive":
        from services.application import ApplicationService
        service = ApplicationService()
        uri = args.uri
        parts = uri.strip("/").split("/")

        if parts[0] == "job-postings" and len(parts) == 2:
            service.archive_job_posting(parts[1])
            print(f"Archived {uri}")
        else:
            print(f"Error: unrecognised URI '{uri}'", file=sys.stderr)
            print("Expected: job-postings/{id}", file=sys.stderr)
            sys.exit(1)
        return

    if args.command == "apply":
        from datetime import datetime
        from services.application import ApplicationService
        service = ApplicationService()
        uri = args.uri
        parts = uri.strip("/").split("/")

        if parts[0] == "job-postings" and len(parts) == 2:
            applied_at = datetime.strptime(args.date, "%Y-%m-%d") if args.date else None
            service.mark_applied(parts[1], args.cv_identifier, applied_at=applied_at)
            print(f"Marked {uri} as applied with {args.cv_identifier}")
        else:
            print(f"Error: unrecognised URI '{uri}'", file=sys.stderr)
            print("Expected: job-postings/{id}", file=sys.stderr)
            sys.exit(1)
        return

    if args.command == "rename":
        from services.application import ApplicationService
        service = ApplicationService()
        uri = args.uri
        parts = uri.strip("/").split("/")

        try:
            if parts[0] == "job-postings" and len(parts) == 2:
                service.rename_job_posting(parts[1], args.new_id)
            elif parts[0] == "cvs" and len(parts) == 2:
                service.rename_cv(parts[1], args.new_id)
            elif parts[0] == "job-postings" and len(parts) == 4 and parts[2] == "cvs":
                service.rename_cv_optimization(parts[1], parts[3], args.new_id)
            else:
                print(f"Error: unrecognised URI '{uri}'", file=sys.stderr)
                print(
                    "Expected: job-postings/{id}, cvs/{id}, or job-postings/{id}/cvs/{id}",
                    file=sys.stderr,
                )
                sys.exit(1)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Renamed {uri} to {args.new_id}")
        return


if __name__ == "__main__":
    main()
