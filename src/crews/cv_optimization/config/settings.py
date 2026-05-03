from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from config.settings import AgentSettings, BaseConfig


class Settings(BaseModel):
    """Top-level configuration model"""

    agents: dict[str, AgentSettings]


class Config(BaseConfig):
    def __init__(self):
        super().__init__(Path(__file__).parent, Settings, "crews.cv_optimization")

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
