"""
Migration: populate optimization-plans.json and cvs.json from record.json files.

Reads every job-postings/{id}/cvs/{id}/record.json and upserts the entry into
collections/optimization-plans.json. If a cv.json exists alongside it, also
upserts an entry into collections/cvs.json using the composite key
(identifier, job_posting_identifier).

Safe to run multiple times. Deletes record.json files after migrating them.

Usage:
    uv run python scripts/migrate_optimization_records.py
    uv run python scripts/migrate_optimization_records.py --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from config.settings import get_data_dir
from repositories import FileSystemRepository


def migrate(data_dir: str, dry_run: bool) -> None:
    repo = FileSystemRepository(data_dir=data_dir)
    job_postings_root = repo.data_dir / "job-postings"

    if not job_postings_root.exists():
        print("No job-postings directory found. Nothing to migrate.")
        return

    migrated = 0
    skipped = 0
    deleted = 0

    for record_path in sorted(job_postings_root.glob("*/cvs/*/record.json")):
        parts = record_path.parts
        job_posting_id = parts[-4]
        opt_id = parts[-2]

        with open(record_path) as f:
            record_data = json.load(f)

        existing = repo.get_cv_optimization_record(job_posting_id, opt_id)
        if existing is not None:
            print(f"  skip  job-postings/{job_posting_id}/cvs/{opt_id} (already in collection)")
            skipped += 1
        else:
            base_cv_id = record_data.get("base_cv_identifier", "")
            print(f"  migrate  job-postings/{job_posting_id}/cvs/{opt_id}")
            if not dry_run:
                repo.add_cv_optimization(job_posting_id, opt_id, base_cv_id)
            migrated += 1

        if not dry_run:
            record_path.unlink()
            deleted += 1

    print()
    print(f"Migrated: {migrated}, skipped: {skipped}, record.json files deleted: {deleted}")
    if dry_run:
        print("(dry run — no changes written)")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without writing")
    args = parser.parse_args()

    migrate(get_data_dir(), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
