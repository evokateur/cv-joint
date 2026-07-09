#!/usr/bin/env python3
"""
Migration: normalize curriculum-vitae.json key order to match the
CurriculumVitae schema's field declaration order.

The qualifications migration appended the new key at the end of each file
instead of in its original position. This round-trips each file through the
CurriculumVitae model so the on-disk key order matches what the app would
write on save.

Safe to run multiple times. Files already in schema order are skipped.

Usage:
    uv run python scripts/migrations/migrate_cv_field_order.py --dry-run
    uv run python scripts/migrations/migrate_cv_field_order.py
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from config.root import get_settings
from models.schema import CurriculumVitae


def migrate_file(path: Path, dry_run: bool) -> bool:
    raw = path.read_text()
    data = json.loads(raw)

    reordered = json.dumps(
        CurriculumVitae(**data).model_dump(mode="json"), indent=2
    )

    if reordered == raw.rstrip("\n"):
        print(f"  skip      {path} (already in order)")
        return False

    print(f"  reorder   {path}")
    if not dry_run:
        path.write_text(reordered + "\n")

    return True


def migrate(data_dir: Path, dry_run: bool) -> None:
    paths = sorted(data_dir.rglob("curriculum-vitae.json"))
    if not paths:
        print("No curriculum-vitae.json files found. Nothing to migrate.")
        return

    migrated = sum(migrate_file(path, dry_run) for path in paths)

    print()
    print(f"Files found: {len(paths)}, reordered: {migrated}")
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
