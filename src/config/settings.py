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

    def __init__(self, config_dir: Path, settings_model: type[BaseModel]):
        load_dotenv()
        yaml_config = load_yaml_config(config_dir)
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

    mcp: dict[str, McpServerSettings]


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
    """Get MCP server configuration by name, or None if not configured or invalid."""
    config_dir = Path(__file__).parent
    yaml_config = load_yaml_config(config_dir)

    if "mcp" not in yaml_config:
        return None

    try:
        config = McpConfig(**yaml_config)
        return config.mcp.get(server_name)
    except Exception:
        return None


def is_mcp_configured(server_name: str = "rag-knowledge") -> bool:
    """Check if an MCP server is fully configured."""
    return get_mcp_config(server_name) is not None
