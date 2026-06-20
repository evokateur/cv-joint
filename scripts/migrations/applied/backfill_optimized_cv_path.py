"""
Migration: backfill `path` field on OptimizedCvRecord entries.

Reads collections/optimized-cvs.json and, for each entry missing a `path`,
looks up the parent JobPostingRecord in collections/job-postings.json and
derives: path = "{parent_path}/cvs/{identifier}"

Safe to run multiple times.

Usage:
    uv run python scripts/migrations/backfill_optimized_cv_path.py
    uv run python scripts/migrations/backfill_optimized_cv_path.py --dry-run
    uv run python scripts/migrations/backfill_optimized_cv_path.py --data-dir /path/to/data --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from config.root import get_settings
from models import OptimizedCvRecord


def default_data_dir() -> str:
    return get_settings().repositories.filesystem.data_dir


def migrate(data_dir: str, dry_run: bool) -> None:
    data = Path(data_dir)
    opt_path = data / "collections" / "optimized-cvs.json"
    jp_path = data / "collections" / "job-postings.json"

    if not opt_path.exists():
        print("No optimized-cvs.json found. Nothing to migrate.")
        return

    with open(opt_path) as f:
        optimized_cvs = json.load(f)

    with open(jp_path) as f:
        job_postings = {item["identifier"]: item for item in json.load(f)}

    updated = 0
    skipped = 0

    for i, entry in enumerate(optimized_cvs):
        if "path" in entry:
            skipped += 1
            continue

        jp_id = entry["job_posting_identifier"]
        parent = job_postings.get(jp_id)
        if parent is None:
            print(f"  WARNING: parent job posting not found for {jp_id}, skipping")
            skipped += 1
            continue

        path = f"{parent['path']}/cvs/{entry['identifier']}"
        optimized_cvs[i] = OptimizedCvRecord(**{**entry, "path": path}).model_dump(mode="json")
        print(f"  backfill  {path}")
        updated += 1

    print()
    print(f"Updated: {updated}, skipped: {skipped}")

    if dry_run:
        print("(dry run — no changes written)")
        return

    with open(opt_path, "w") as f:
        json.dump(optimized_cvs, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--data-dir", metavar="PATH", help="Path to data directory")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without writing")
    args = parser.parse_args()

    migrate(args.data_dir or default_data_dir(), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
