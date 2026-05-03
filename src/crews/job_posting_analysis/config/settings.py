from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from config.settings import AgentSettings, BaseConfig


class Settings(BaseModel):
    """Top-level configuration model"""

    agents: dict[str, AgentSettings]


class Config(BaseConfig):
    def __init__(self):
        super().__init__(Path(__file__).parent, Settings, "crews.job_posting_analysis")

    @property
    def job_analyst_model(self) -> str:
        return self._get_agent_setting("job_analyst", "model")

    @property
    def job_analyst_temperature(self) -> str:
        return str(self._get_agent_setting("job_analyst", "temperature"))

    @property
    def job_analyst_max_tokens(self) -> Optional[int]:
        return self._get_agent_setting("job_analyst", "max_tokens")


def get_config() -> Config:
    return Config()
