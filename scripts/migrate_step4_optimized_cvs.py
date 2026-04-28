#!/usr/bin/env python3
"""
Step 4 migration: consolidate optimization-plans.json + optimized CV entries in cvs.json
into a new optimized-cvs.json collection, and backfill _type fields in artifact JSON files.

Run from the project root:
    uv run python scripts/migrate_step4_optimized_cvs.py [--data-dir PATH] [--dry-run]

Defaults to the configured data directory if --data-dir is not given.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def load_json(path: Path) -> list | dict:
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def write_json(path: Path, data, dry_run: bool):
    if dry_run:
        print(f"  [dry-run] would write {path}")
    else:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  wrote {path}")


def migrate(data_dir: Path, dry_run: bool):
    collections_dir = data_dir / "collections"
    plans_path = collections_dir / "optimization-plans.json"
    cvs_path = collections_dir / "cvs.json"
    optimized_cvs_path = collections_dir / "optimized-cvs.json"

    if not plans_path.exists():
        print("optimization-plans.json not found — already migrated or no data.")
        return

    plans = load_json(plans_path)
    cvs = load_json(cvs_path)

    # Index cvs by (identifier, job_posting_identifier) for fast lookup
    opt_cv_index = {
        (item["identifier"], item.get("job_posting_identifier")): item
        for item in cvs
        if item.get("job_posting_identifier")
    }

    # Build optimized-cvs.json records
    optimized_records = []
    for plan in plans:
        identifier = plan["identifier"]
        jp_id = plan["job_posting_identifier"]
        base_cv_id = plan["base_cv_identifier"]

        # Read name/profession from the cv.json artifact
        cv_path = data_dir / "job-postings" / jp_id / "cvs" / identifier / "cv.json"
        name, profession = "", ""
        if cv_path.exists():
            cv_data = load_json(cv_path)
            name = cv_data.get("name", "")
            profession = cv_data.get("profession", "")
        else:
            print(f"  warning: cv.json not found for {jp_id}/cvs/{identifier}")

        record = {
            "identifier": identifier,
            "job_posting_identifier": jp_id,
            "base_cv_identifier": base_cv_id,
            "name": name,
            "profession": profession,
            "job_title": plan.get("job_title"),
            "company": plan.get("company"),
            "created_at": plan["created_at"],
            "updated_at": plan.get("updated_at", plan["created_at"]),
        }
        optimized_records.append(record)
        print(f"  migrated optimization: {jp_id}/cvs/{identifier} ({name})")

    # Write optimized-cvs.json
    print(f"\nWriting {optimized_cvs_path}...")
    write_json(optimized_cvs_path, optimized_records, dry_run)

    # Strip optimized CV entries from cvs.json
    base_cvs = [item for item in cvs if not item.get("job_posting_identifier")]
    print(f"\nStripping {len(cvs) - len(base_cvs)} optimized entries from cvs.json "
          f"({len(base_cvs)} base CVs remain)...")
    write_json(cvs_path, base_cvs, dry_run)

    # Delete optimization-plans.json
    print(f"\nDeleting {plans_path}...")
    if dry_run:
        print(f"  [dry-run] would delete {plans_path}")
    else:
        plans_path.unlink()
        print(f"  deleted {plans_path}")

    # Backfill _type fields in artifact JSON files
    print("\nBackfilling _type fields in optimization artifact files...")
    backfill_map = {
        "cv.json": "CurriculumVitae",
        "transformation-plan.json": "CvTransformationPlan",
    }
    for jp_dir in (data_dir / "job-postings").iterdir():
        cvs_dir = jp_dir / "cvs"
        if not cvs_dir.exists():
            continue
        for opt_dir in cvs_dir.iterdir():
            for filename, type_name in backfill_map.items():
                artifact = opt_dir / filename
                if not artifact.exists():
                    continue
                data = load_json(artifact)
                if "_type" in data:
                    continue  # already has _type
                data["_type"] = type_name
                print(f"  backfilling _type={type_name!r} in {artifact.relative_to(data_dir)}")
                write_json(artifact, data, dry_run)

    print("\nMigration complete.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", metavar="PATH", help="Path to data directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without writing")
    args = parser.parse_args()

    if args.data_dir:
        data_dir = Path(args.data_dir).expanduser()
    else:
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from repositories.config.settings import get_config
        data_dir = Path(get_config().data_dir).expanduser()

    if not data_dir.exists():
        print(f"Error: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Data directory: {data_dir}")
    if args.dry_run:
        print("(dry run — no files will be modified)\n")
    else:
        print()

    migrate(data_dir, args.dry_run)


if __name__ == "__main__":
    main()
