from typing import Optional
from pydantic import BaseModel
from config.settings import AgentSettings, CrewSettings


class Settings(BaseModel):
    """Top-level configuration model"""

    agents: dict[str, AgentSettings]


class Config:
    def __init__(self, settings: CrewSettings | None = None):
        if settings is None:
            from config.root import get_settings

            settings = get_settings().crews["cv_optimization"]
        self._settings = settings

    def _get_agent_setting(self, agent_name: str, setting: str):
        agent = self._settings.agents.get(agent_name)
        if agent is None:
            raise ValueError(f"Agent '{agent_name}' not found in settings.yaml")
        return getattr(agent, setting)

    @property
    def cv_strategist_model(self) -> str:
        return self._get_agent_setting("cv_strategist", "model")

    @property
    def cv_rewriter_model(self) -> str:
        return self._get_agent_setting("cv_rewriter", "model")

    @property
    def cv_strategist_temperature(self) -> str:
        return str(self._get_agent_setting("cv_strategist", "temperature"))

    @property
    def cv_strategist_max_tokens(self) -> Optional[int]:
        return self._get_agent_setting("cv_strategist", "max_tokens")

    @property
    def cv_rewriter_temperature(self) -> str:
        return str(self._get_agent_setting("cv_rewriter", "temperature"))

    @property
    def cv_rewriter_max_tokens(self) -> Optional[int]:
        return self._get_agent_setting("cv_rewriter", "max_tokens")


def get_config() -> Config:
    return Config()
