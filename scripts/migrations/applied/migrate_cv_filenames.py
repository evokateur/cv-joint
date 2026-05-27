#!/usr/bin/env python3
"""
Migrate job-posting and CV collection records:
  - rename filepath key to path
  - strip filename from value (store directory only)
  - rename cv.json → curriculum-vitae.json
  - rename cv.md  → curriculum-vitae.md
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from repositories.config.settings import get_config

DATA_DIR = Path(get_config().data_dir).expanduser()


def migrate_collection(collection_path: Path):
    records = json.loads(collection_path.read_text())
    for record in records:
        if "filepath" in record:
            old_value = record.pop("filepath")
            record["path"] = str(Path(old_value).parent)
    collection_path.write_text(json.dumps(records, indent=2))
    print(f"Updated {collection_path.name}")


def rename_cv_files():
    cvs_dir = DATA_DIR / "cvs"
    for cv_dir in cvs_dir.iterdir():
        if not cv_dir.is_dir():
            continue
        for old_name, new_name in [
            ("cv.json", "curriculum-vitae.json"),
            ("cv.md", "curriculum-vitae.md"),
        ]:
            old = cv_dir / old_name
            new = cv_dir / new_name
            if old.exists() and not new.exists():
                old.rename(new)
                print(f"  {old_name} → {new_name} ({cv_dir.name})")


migrate_collection(DATA_DIR / "collections" / "job-postings.json")
migrate_collection(DATA_DIR / "collections" / "cvs.json")
rename_cv_files()
print("Done.")
