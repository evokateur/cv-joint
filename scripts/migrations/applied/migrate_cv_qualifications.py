#!/usr/bin/env python3
"""
Migration: CurriculumVitae.summary_of_qualifications (str) -> qualifications (list[str]).

Finds every curriculum-vitae.json under the data directory and wraps the
existing summary_of_qualifications string as a single-item qualifications list.

Safe to run multiple times. Files that already have a "qualifications" key
are skipped.

Usage:
    uv run python scripts/migrations/migrate_cv_qualifications.py --dry-run
    uv run python scripts/migrations/migrate_cv_qualifications.py
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from config.root import get_settings


def migrate_file(path: Path, dry_run: bool) -> bool:
    data = json.loads(path.read_text())

    if "qualifications" in data:
        print(f"  skip      {path} (already migrated)")
        return False
    if "summary_of_qualifications" not in data:
        print(f"  warning   {path} (no summary_of_qualifications key)")
        return False

    summary = data.pop("summary_of_qualifications")
    data["qualifications"] = [summary]

    print(f"  migrate   {path}")
    if not dry_run:
        path.write_text(json.dumps(data, indent=2))

    return True


def migrate(data_dir: Path, dry_run: bool) -> None:
    paths = sorted(data_dir.rglob("curriculum-vitae.json"))
    if not paths:
        print("No curriculum-vitae.json files found. Nothing to migrate.")
        return

    migrated = sum(migrate_file(path, dry_run) for path in paths)

    print()
    print(f"Files found: {len(paths)}, migrated: {migrated}")
    if dry_run:
        print("(dry run - no changes written)")


def default_data_dir() -> Path:
    return Path(get_settings().repositories.filesystem.data_dir).expanduser()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--data-dir", metavar="PATH", help="Path to data directory")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print what would happen without writing"
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser() if args.data_dir else default_data_dir()
    if not data_dir.exists():
        print(f"Error: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Data directory: {data_dir}")
    if args.dry_run:
        print("(dry run - no files will be modified)")
    print()

    migrate(data_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
