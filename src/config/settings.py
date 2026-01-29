"""
Shared configuration utilities and models.

Base utilities (AgentSettings, ChatSettings, BaseConfig, load_yaml_config) are defined here
and imported by analyzer crews for their own settings.
"""

from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import yaml


class AgentSettings(BaseModel):
    """Configuration for a single agent"""

    model: str = Field(min_length=1, description="LLM model name")
    temperature: float = Field(ge=0.0, le=2.0, description="LLM temperature (0.0-2.0)")


class ChatSettings(BaseModel):
    """Configuration for chat/conversation models"""

    model: str = Field(min_length=1, description="LLM model name for chat")
    temperature: float = Field(ge=0.0, le=2.0, description="LLM temperature (0.0-2.0)")


class McpServerSettings(BaseModel):
    """Configuration for an MCP server"""

    command: str = Field(description="Command to run the MCP server")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    tool_name: str = Field(alias="x-tool-name", description="Name of the search tool to call")


USER_CONFIG_FILE = Path.home() / ".cv-joint" / "settings.yaml"


def load_yaml_config(config_dir: Path, user_config_path: Optional[str] = None) -> dict:
    """Load settings from YAML files with override hierarchy:
    settings.yaml -> ~/.cv-joint/settings.yaml -> settings.local.yaml

    YAML files are the single source of truth for configuration.
    Environment variables are only used for API keys (secrets).

    Args:
        config_dir: Directory containing settings.yaml and optional settings.local.yaml
        user_config_path: Dot-separated path to extract from user config (e.g., "crews.cv_analysis")
    """
    settings_file = config_dir / "settings.yaml"
    local_settings_file = config_dir / "settings.local.yaml"

    if not settings_file.exists():
        raise FileNotFoundError(f"Required settings file not found: {settings_file}")

    with open(settings_file) as f:
        config = yaml.safe_load(f) or {}

    if USER_CONFIG_FILE.exists():
        with open(USER_CONFIG_FILE) as f:
            user_config = yaml.safe_load(f) or {}
            if user_config_path:
                for key in user_config_path.split("."):
                    user_config = user_config.get(key, {})
                    if not isinstance(user_config, dict):
                        user_config = {}
                        break
            deep_merge(config, user_config)

    if local_settings_file.exists():
        with open(local_settings_file) as f:
            local_config = yaml.safe_load(f) or {}
            deep_merge(config, local_config)

    return expand_tildes(config)


def expand_tildes(config: dict) -> dict:
    """Recursively expand ~/ in string values to home directory paths."""
    result = {}
    for key, value in config.items():
        if isinstance(value, dict):
            result[key] = expand_tildes(value)
        elif isinstance(value, list):
            result[key] = [
                str(Path(item).expanduser()) if isinstance(item, str) and item.startswith("~/")
                else expand_tildes(item) if isinstance(item, dict)
                else item
                for item in value
            ]
        elif isinstance(value, str) and value.startswith("~/"):
            result[key] = str(Path(value).expanduser())
        else:
            result[key] = value
    return result


def deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override dict into base dict"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value


class BaseConfig:
    """Base configuration class with common initialization and agent setting access"""

    def __init__(
        self,
        config_dir: Path,
        settings_model: type[BaseModel],
        user_config_path: Optional[str] = None,
    ):
        load_dotenv()
        yaml_config = load_yaml_config(config_dir, user_config_path)
        self._settings = settings_model(**yaml_config)

    def _get_agent_setting(self, agent_name: str, setting: str):
        """Get agent setting from validated Pydantic model"""
        agent = self._settings.agents.get(agent_name)
        if agent is None:
            raise ValueError(f"Agent '{agent_name}' not found in settings.yaml")
        return getattr(agent, setting)


# Separate config models for independent validation


class ChatConfig(BaseModel):
    """Chat configuration - validated independently"""

    chat: ChatSettings


class McpConfig(BaseModel):
    """MCP configuration - validated independently"""

    mcp: dict[str, Optional[McpServerSettings]] = Field(alias="mcpServers")


def get_chat_config() -> dict:
    """Get chat configuration from YAML, validated with Pydantic"""
    config_dir = Path(__file__).parent
    yaml_config = load_yaml_config(config_dir)
    config = ChatConfig(**yaml_config)

    return {
        "model": config.chat.model,
        "temperature": config.chat.temperature,
    }


def get_mcp_config(server_name: str) -> Optional[McpServerSettings]:
    """Get MCP server configuration by name, or None if not configured."""
    config_dir = Path(__file__).parent
    yaml_config = load_yaml_config(config_dir)
    config = McpConfig(**yaml_config)
    return config.mcp.get(server_name)


def is_mcp_configured(server_name: str = "rag-knowledge") -> bool:
    """Check if an MCP server is fully configured."""
    return get_mcp_config(server_name) is not None


def get_merged_config() -> dict:
    """Get fully merged configuration from all sources for display.

    Collects configs from:
    - src/config/settings.yaml (chat, mcp)
    - src/crews/*/config/settings.yaml (crew-specific agents)
    - src/repositories/config/settings.yaml (repository settings)
    - ~/.cv-joint/settings.yaml (user overrides)

    Returns nested dict with explicit paths for user config format.
    """
    config_dir = Path(__file__).parent
    src_dir = config_dir.parent
    crews_dir = src_dir / "crews"
    repositories_dir = src_dir / "repositories"

    merged = {}

    base_config = load_yaml_config(config_dir)
    deep_merge(merged, base_config)

    if crews_dir.exists():
        for crew_dir in crews_dir.iterdir():
            crew_settings = crew_dir / "config" / "settings.yaml"
            if crew_settings.exists():
                crew_config = load_yaml_config(crew_dir / "config", f"crews.{crew_dir.name}")
                if "crews" not in merged:
                    merged["crews"] = {}
                merged["crews"][crew_dir.name] = crew_config

    repositories_settings = repositories_dir / "config" / "settings.yaml"
    if repositories_settings.exists():
        repo_config = load_yaml_config(repositories_dir / "config", "repositories")
        merged["repositories"] = repo_config

    return merged
