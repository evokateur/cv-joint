from pydantic import BaseModel


class FilesystemRepositorySettings(BaseModel):
    data_dir: str


class RepositoriesSettings(BaseModel):
    filesystem: FilesystemRepositorySettings


class Config:
    def __init__(self, settings: RepositoriesSettings | None = None):
        if settings is None:
            from config.root import get_settings

            settings = get_settings().repositories
        self._settings = settings

    @property
    def data_dir(self) -> str:
        return self._settings.filesystem.data_dir


def get_config() -> Config:
    return Config()
