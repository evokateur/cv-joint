from pathlib import Path
from pydantic import BaseModel
from config.settings import BaseConfig


class FilesystemRepositorySettings(BaseModel):
    data_dir: str


class Settings(BaseModel):
    filesystem: FilesystemRepositorySettings


class Config(BaseConfig):
    def __init__(self):
        super().__init__(Path(__file__).parent, Settings, "repositories")

    @property
    def data_dir(self) -> str:
        return self._settings.filesystem.data_dir


def get_config() -> Config:
    return Config()
