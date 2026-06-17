from typing import Optional
from pydantic import BaseModel
from config.settings import AgentSettings, CrewSettings


class Config:
    def __init__(self, settings: CrewSettings | None = None):
        if settings is None:
            from config.root import get_settings

            settings = get_settings().crews["cv_analysis"]
        self._settings = settings

    def _get_agent_setting(self, agent_name: str, setting: str):
        agent = self._settings.agents.get(agent_name)
        if agent is None:
            raise ValueError(f"Agent '{agent_name}' not found in settings.yaml")
        return getattr(agent, setting)

    @property
    def cv_analyst_model(self) -> str:
        return self._get_agent_setting("cv_analyst", "model")

    @property
    def cv_analyst_temperature(self) -> str:
        return str(self._get_agent_setting("cv_analyst", "temperature"))

    @property
    def cv_analyst_max_tokens(self) -> Optional[int]:
        return self._get_agent_setting("cv_analyst", "max_tokens")


def get_config() -> Config:
    return Config()
