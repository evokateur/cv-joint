#!/usr/bin/env python3
"""
Migration: populate JobPostingRecord location and transitions.

Reads collections/job-postings.json, derives each record's new location from
legacy is_archived/applied_at fields, moves job-posting directories into the
location-aware layout, repairs optimized CV paths that live under moved job
postings, and writes updated collections once at the end.

Safe to run multiple times. Records that already have a raw "transitions" key
are skipped.

Usage:
    uv run python scripts/migrations/migrate_job_posting_locations.py --dry-run
    uv run python scripts/migrations/migrate_job_posting_locations.py
"""

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from config.root import get_settings


@dataclass(frozen=True)
class PlannedRecord:
    index: int
    identifier: str
    old_path: str
    new_path: str
    location: str | None
    transitions: list[dict[str, Any]]


@dataclass(frozen=True)
class PlannedOptimizedCv:
    index: int
    job_posting_identifier: str
    identifier: str
    old_path: str | None
    new_path: str


def load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def write_json(path: Path, data: list[dict[str, Any]]) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def canonical_path(identifier: str, location: str | None) -> str:
    if location:
        return f"job-postings/{location}/{identifier}"
    return f"job-postings/{identifier}"


def applied_transition(record: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "date": record["applied_at"],
        "location": "applied",
        "applied_at": record["applied_at"],
    }
    if record.get("applied_with"):
        entry["applied_with"] = record["applied_with"]
    return entry


def archived_transition(record: dict[str, Any]) -> dict[str, Any]:
    return {"date": record["updated_at"], "location": "archived"}


def derive_location_and_transitions(
    record: dict[str, Any],
) -> tuple[str | None, list[dict[str, Any]]]:
    is_archived = record.get("is_archived", False)
    applied_at = record.get("applied_at")

    if is_archived and applied_at:
        return "archived", [applied_transition(record), archived_transition(record)]
    if is_archived:
        return "archived", [archived_transition(record)]
    if applied_at:
        return "applied", [applied_transition(record)]
    return None, []


def plan_migration(records: list[dict[str, Any]]) -> tuple[list[PlannedRecord], int]:
    planned = []
    skipped = 0

    for index, record in enumerate(records):
        identifier = record["identifier"]
        if "transitions" in record:
            print(f"  skip      {identifier} (already has transitions)")
            skipped += 1
            continue

        location, transitions = derive_location_and_transitions(record)
        old_path = record["path"]
        new_path = canonical_path(identifier, location)
        planned.append(
            PlannedRecord(
                index=index,
                identifier=identifier,
                old_path=old_path,
                new_path=new_path,
                location=location,
                transitions=transitions,
            )
        )

    return planned, skipped


def validate_moves(data_dir: Path, planned: list[PlannedRecord]) -> None:
    destinations = {}
    for item in planned:
        if item.old_path == item.new_path:
            continue

        source = data_dir / item.old_path
        destination = data_dir / item.new_path
        if not source.exists():
            raise FileNotFoundError(f"Source directory not found: {source}")
        if destination.exists():
            raise FileExistsError(f"Destination already exists: {destination}")
        if destination.is_relative_to(source):
            raise ValueError(f"Destination is inside source: {source} -> {destination}")
        if item.new_path in destinations:
            raise ValueError(
                f"Duplicate destination {item.new_path} for "
                f"{destinations[item.new_path]} and {item.identifier}"
            )
        destinations[item.new_path] = item.identifier


def print_plan(planned: list[PlannedRecord]) -> None:
    for item in planned:
        transition_names = " -> ".join(
            transition["location"] for transition in item.transitions
        )
        if not transition_names:
            transition_names = "none"

        if item.old_path == item.new_path:
            print(
                f"  update    {item.identifier}: "
                f"location={item.location!r}, transitions={transition_names}"
            )
        else:
            print(
                f"  move      {item.old_path} -> {item.new_path}; "
                f"location={item.location!r}, transitions={transition_names}"
            )


def future_job_posting_paths(
    records: list[dict[str, Any]], planned: list[PlannedRecord]
) -> dict[str, str]:
    paths = {record["identifier"]: record["path"] for record in records}
    for item in planned:
        paths[item.identifier] = item.new_path
    return paths


def plan_optimized_cvs(
    records: list[dict[str, Any]], job_posting_paths: dict[str, str]
) -> tuple[list[PlannedOptimizedCv], int]:
    planned = []
    skipped = 0

    for index, record in enumerate(records):
        job_posting_identifier = record["job_posting_identifier"]
        identifier = record["identifier"]
        parent_path = job_posting_paths.get(job_posting_identifier)

        if parent_path is None:
            print(
                f"  warning   optimized CV parent not found: "
                f"{job_posting_identifier}/cvs/{identifier}"
            )
            skipped += 1
            continue

        new_path = f"{parent_path}/cvs/{identifier}"
        old_path = record.get("path")
        if old_path == new_path:
            skipped += 1
            continue

        planned.append(
            PlannedOptimizedCv(
                index=index,
                job_posting_identifier=job_posting_identifier,
                identifier=identifier,
                old_path=old_path,
                new_path=new_path,
            )
        )

    return planned, skipped


def validate_optimized_cv_paths(
    data_dir: Path, planned: list[PlannedOptimizedCv]
) -> None:
    for item in planned:
        if item.old_path is None:
            continue
        if not (data_dir / item.old_path).is_dir():
            raise FileNotFoundError(
                f"Optimized CV directory not found at current path: {item.old_path}"
            )


def print_optimized_cv_plan(planned: list[PlannedOptimizedCv]) -> None:
    for item in planned:
        print(
            f"  repair    {item.job_posting_identifier}/cvs/{item.identifier}: "
            f"{item.old_path!r} -> {item.new_path!r}"
        )


def apply_migration(
    data_dir: Path,
    job_postings_collection_path: Path,
    job_postings: list[dict[str, Any]],
    planned_job_postings: list[PlannedRecord],
    optimized_cvs_collection_path: Path,
    optimized_cvs: list[dict[str, Any]],
    planned_optimized_cvs: list[PlannedOptimizedCv],
) -> None:
    for item in planned_job_postings:
        if item.old_path != item.new_path:
            destination = data_dir / item.new_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(data_dir / item.old_path), str(destination))

        record = job_postings[item.index]
        record["path"] = item.new_path
        record["location"] = item.location
        record["transitions"] = item.transitions

    for item in planned_optimized_cvs:
        optimized_cvs[item.index]["path"] = item.new_path

    write_json(job_postings_collection_path, job_postings)
    if planned_optimized_cvs:
        write_json(optimized_cvs_collection_path, optimized_cvs)


def migrate(data_dir: Path, dry_run: bool) -> None:
    job_postings_collection_path = data_dir / "collections" / "job-postings.json"
    optimized_cvs_collection_path = data_dir / "collections" / "optimized-cvs.json"

    job_postings = load_json(job_postings_collection_path)
    if not job_postings:
        print("No job-postings.json found. Nothing to migrate.")
        return
    optimized_cvs = load_json(optimized_cvs_collection_path)

    planned_job_postings, skipped_job_postings = plan_migration(job_postings)
    validate_moves(data_dir, planned_job_postings)

    job_posting_paths = future_job_posting_paths(job_postings, planned_job_postings)
    planned_optimized_cvs, skipped_optimized_cvs = plan_optimized_cvs(
        optimized_cvs, job_posting_paths
    )
    validate_optimized_cv_paths(data_dir, planned_optimized_cvs)

    print_plan(planned_job_postings)
    print_optimized_cv_plan(planned_optimized_cvs)

    print()
    print(
        f"Job postings planned: {len(planned_job_postings)}, "
        f"skipped: {skipped_job_postings}"
    )
    print(
        f"Optimized CV paths planned: {len(planned_optimized_cvs)}, "
        f"skipped: {skipped_optimized_cvs}"
    )

    if dry_run:
        print("(dry run - no changes written)")
        return

    apply_migration(
        data_dir,
        job_postings_collection_path,
        job_postings,
        planned_job_postings,
        optimized_cvs_collection_path,
        optimized_cvs,
        planned_optimized_cvs,
    )
    print(f"Wrote {job_postings_collection_path}")
    if planned_optimized_cvs:
        print(f"Wrote {optimized_cvs_collection_path}")


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
