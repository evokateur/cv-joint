from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
import yaml


class AgentSettings(BaseModel):
    """Configuration for a single agent"""

    model: str = Field(min_length=1, description="LLM model name")
    temperature: float = Field(ge=0.0, le=2.0, description="LLM temperature (0.0-2.0)")


class RagSettings(BaseModel):
    """Configuration for RAG (Retrieval-Augmented Generation)"""

    embedding_model: str = Field(min_length=1)
    collection_name: str = Field(min_length=1)
    num_results: int = Field(gt=0, description="Number of results to retrieve")
    chunk_size: int = Field(ge=100, description="Chunk size for text splitting")
    chunk_overlap: int = Field(ge=0, description="Overlap between chunks")

    @field_validator("chunk_overlap")
    @classmethod
    def overlap_less_than_size(cls, v, info):
        if "chunk_size" in info.data and v >= info.data["chunk_size"]:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return v


class PathSettings(BaseModel):
    """Configuration for file paths"""

    knowledge_base: str
    vector_db: str


class SettingsModel(BaseModel):
    agents: dict[str, AgentSettings]
    rag: RagSettings
    paths: PathSettings


def load_yaml_config(config_dir: Path) -> dict:
    """Load settings from YAML files with override hierarchy:
    settings.yaml -> settings.local.yaml

    YAML files are the single source of truth for configuration.
    Environment variables are only used for API keys (secrets).
    """
    settings_file = config_dir / "settings.yaml"
    local_settings_file = config_dir / "settings.local.yaml"

    if not settings_file.exists():
        raise FileNotFoundError(f"Required settings file not found: {settings_file}")

    with open(settings_file) as f:
        config = yaml.safe_load(f) or {}

    if local_settings_file.exists():
        with open(local_settings_file) as f:
            local_config = yaml.safe_load(f) or {}
            deep_merge(config, local_config)

    return config


def deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override dict into base dict"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value


class BaseConfig:
    """Base configuration class with common initialization and agent setting access"""

    def __init__(self, config_dir: Path, settings_model: type[SettingsModel]):
        load_dotenv()
        yaml_config = load_yaml_config(config_dir)
        self._settings = settings_model(**yaml_config)

    def _get_agent_setting(self, agent_name: str, setting: str):
        """Get agent setting from validated Pydantic model"""
        agent = self._settings.agents.get(agent_name)
        if agent is None:
            raise ValueError(f"Agent '{agent_name}' not found in settings.yaml")
        return getattr(agent, setting)
