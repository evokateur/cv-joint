"""Shared configuration models and utilities used by config.root and typed settings."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentSettings(BaseModel):
    """Configuration for a single agent"""

    model: str = Field(min_length=1, description="LLM model name")
    temperature: float = Field(ge=0.0, le=2.0, description="LLM temperature (0.0-2.0)")
    max_tokens: Optional[int] = Field(default=4096, description="Maximum tokens for LLM response")


class CrewSettings(BaseModel):
    """Configuration for a crew's agents."""

    agents: dict[str, AgentSettings]


class ChatSettings(BaseModel):
    """Configuration for chat/conversation models"""

    model: str = Field(min_length=1, description="LLM model name for chat")
    temperature: float = Field(ge=0.0, le=2.0, description="LLM temperature (0.0-2.0)")


class McpServerSettings(BaseModel):
    """Configuration for an MCP server"""

    model_config = ConfigDict(populate_by_name=True)

    command: str = Field(description="Command to run the MCP server")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables"
    )
    tool_name: str = Field(
        alias="x-tool-name", description="Name of the search tool to call"
    )


USER_CONFIG_FILE = Path.home() / ".cv-joint" / "settings.yaml"


def expand_tildes(config: dict) -> dict:
    """Recursively expand ~/ in string values to home directory paths."""
    result = {}
    for key, value in config.items():
        if isinstance(value, dict):
            result[key] = expand_tildes(value)
        elif isinstance(value, list):
            result[key] = [
                str(Path(item).expanduser())
                if isinstance(item, str) and item.startswith("~/")
                else expand_tildes(item)
                if isinstance(item, dict)
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
