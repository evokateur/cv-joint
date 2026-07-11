import json
import re
from pathlib import Path

from models import DOMAIN_OBJECT_REGISTRY


def _to_kebab_case(name: str) -> str:
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1-\2", s1).lower()


def export_json_schemas(schema_dir: Path) -> list[Path]:
    """Write one JSON Schema file per domain object model into schema_dir."""
    schema_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for name, model in DOMAIN_OBJECT_REGISTRY.items():
        path = schema_dir / f"{_to_kebab_case(name)}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2))
        paths.append(path)

    return paths
