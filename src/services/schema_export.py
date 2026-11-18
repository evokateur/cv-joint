import json
from pathlib import Path

from models import DOMAIN_OBJECT_REGISTRY, kebab_case


def export_json_schemas(schema_dir: Path) -> list[Path]:
    """Write one JSON Schema file per domain object model into schema_dir."""
    schema_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for name, model in DOMAIN_OBJECT_REGISTRY.items():
        path = schema_dir / f"{kebab_case(name)}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2))
        paths.append(path)

    return paths
