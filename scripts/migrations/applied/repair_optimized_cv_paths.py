#!/usr/bin/env python3
"""
Migration: repair stale `path` fields on OptimizedCvRecord entries (CJ-48).

An optimized CV's stored path should be "{parent_path}/cvs/{identifier}".
Records drift from that when a parent job posting was filed before nested
paths were kept in sync, or when an optimized CV was renamed (the rename
moved the directory but kept the old path).

For each drifted record whose expected directory exists, this sets the
record's path to the expected value. All existing files and directories
are preserved, including those at the old path. Missing expected
directories are reported and skipped.

Run `cv-joint export-markdown` afterwards to refresh front matter.

Safe to run multiple times.

Usage:
    uv run python scripts/migrations/applied/repair_optimized_cv_paths.py --dry-run
    uv run python scripts/migrations/applied/repair_optimized_cv_paths.py
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from config.root import get_settings
from models import OptimizedCvRecord


def migrate(data_dir: Path, dry_run: bool) -> None:
    optimized_cvs_path = data_dir / "collections" / "optimized-cvs.json"
    job_postings_path = data_dir / "collections" / "job-postings.json"

    optimized_cvs = json.loads(optimized_cvs_path.read_text())
    job_postings = {
        item["identifier"]: item for item in json.loads(job_postings_path.read_text())
    }

    repaired = skipped = warnings = 0

    for i, entry in enumerate(optimized_cvs):
        parent = job_postings.get(entry["job_posting_identifier"])
        if parent is None:
            print(f"  WARNING   parent not found: {entry['job_posting_identifier']}")
            warnings += 1
            continue

        stored = entry["path"]
        expected = f"{parent['path']}/cvs/{entry['identifier']}"
        if stored == expected:
            skipped += 1
            continue

        if not (data_dir / expected).exists():
            print(f"  WARNING   expected directory missing: {expected}")
            warnings += 1
            continue

        print(f"  repair    {stored} → {expected}")
        optimized_cvs[i] = OptimizedCvRecord(
            **{**entry, "path": expected}
        ).model_dump(mode="json")
        repaired += 1

    print()
    print(
        f"Repaired: {repaired}, skipped: {skipped}, warnings: {warnings}"
    )

    if dry_run:
        print("(dry run - no changes written)")
        return

    optimized_cvs_path.write_text(json.dumps(optimized_cvs, indent=2))


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
    print()

    migrate(data_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
