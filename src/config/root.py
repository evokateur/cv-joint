"""Central configuration loading pipeline for runtime settings."""

from functools import lru_cache
from pathlib import Path
import copy

from dotenv import load_dotenv
import yaml

import config.settings as shared_settings


CONFIG_DIR = Path(__file__).parent
CREWS_DIR = CONFIG_DIR.parent / "crews"
REPOSITORIES_DIR = CONFIG_DIR.parent / "repositories"


def _read_yaml_file(path: Path, *, required: bool = False) -> dict:
    """Read a YAML file with PyYAML and return a dictionary."""
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required settings file not found: {path}")
        return {}

    with open(path) as f:
        return yaml.safe_load(f) or {}


def _merge_local_override(merged: dict, config_dir: Path, namespace: list[str]) -> None:
    """Apply a module-local override file into the requested namespace."""
    override = _read_yaml_file(config_dir / "settings.local.yaml")
    if not override:
        return

    target = merged
    for key in namespace:
        target = target.setdefault(key, {})
    shared_settings.deep_merge(target, override)


def _load_default_tree() -> dict:
    """Assemble module-local defaults into explicit namespaces."""
    merged = _read_yaml_file(CONFIG_DIR / "settings.yaml", required=True)

    crews: dict[str, dict] = {}
    if CREWS_DIR.exists():
        for crew_dir in sorted(CREWS_DIR.iterdir(), key=lambda item: item.name):
            settings_file = crew_dir / "config" / "settings.yaml"
            if settings_file.exists():
                crews[crew_dir.name] = _read_yaml_file(settings_file, required=True)
    if crews:
        merged["crews"] = crews

    repository_settings = REPOSITORIES_DIR / "config" / "settings.yaml"
    if repository_settings.exists():
        merged["repositories"] = _read_yaml_file(repository_settings, required=True)

    return merged


_MOUNTED_NAMESPACES = frozenset({"crews", "repositories"})


def _apply_local_overrides(merged: dict) -> None:
    """Apply module-local settings.local.yaml files after user overrides."""
    root_override = _read_yaml_file(CONFIG_DIR / "settings.local.yaml")
    if root_override:
        scoped = {k: v for k, v in root_override.items() if k not in _MOUNTED_NAMESPACES}
        if scoped:
            shared_settings.deep_merge(merged, scoped)

    if CREWS_DIR.exists():
        for crew_dir in sorted(CREWS_DIR.iterdir(), key=lambda item: item.name):
            config_dir = crew_dir / "config"
            if (config_dir / "settings.yaml").exists():
                _merge_local_override(merged, config_dir, ["crews", crew_dir.name])

    repo_config_dir = REPOSITORIES_DIR / "config"
    if (repo_config_dir / "settings.yaml").exists():
        _merge_local_override(merged, repo_config_dir, ["repositories"])


@lru_cache(maxsize=1)
def _load_merged_config() -> dict:
    """Load the merged runtime configuration once per process."""
    load_dotenv()

    merged = _load_default_tree()
    user_config = _read_yaml_file(shared_settings.USER_CONFIG_FILE)
    shared_settings.deep_merge(merged, user_config)
    _apply_local_overrides(merged)

    return shared_settings.expand_tildes(merged)


def get_merged_config() -> dict:
    """Return the merged config in the raw display shape."""
    return copy.deepcopy(_load_merged_config())
