#!/usr/bin/env python3
"""
Fix collection records written by migrate_cv_filenames.py:
  - normalize field order to match Pydantic model definition
  - remove null-valued optional fields
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from repositories.config.settings import get_config
from models.schema import JobPostingRecord, CurriculumVitaeRecord

DATA_DIR = Path(get_config().data_dir).expanduser()


def normalize_collection(collection_path: Path, model_class):
    records = json.loads(collection_path.read_text())
    normalized = [
        model_class(**record).model_dump(mode="json", exclude_none=True)
        for record in records
    ]
    collection_path.write_text(json.dumps(normalized, indent=2))
    print(f"Normalized {collection_path.name} ({len(normalized)} records)")


normalize_collection(DATA_DIR / "collections" / "job-postings.json", JobPostingRecord)
normalize_collection(DATA_DIR / "collections" / "cvs.json", CurriculumVitaeRecord)
print("Done.")
