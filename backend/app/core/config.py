from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KADR_", case_sensitive=False)

    database_url: str = "sqlite+aiosqlite:///./data/kadr.db"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=list)
    tmdb_access_token: SecretStr | None = None
    tmdb_base_url: str = "https://api.themoviedb.org/3"
    tmdb_image_base_url: str = "https://image.tmdb.org/t/p"
    tmdb_language: str = "ru-RU"
    tmdb_region: str = "RU"
    tmdb_timeout_seconds: float = Field(default=8, gt=0, le=30)
    metadata_cache_ttl_seconds: int = Field(default=21_600, ge=300, le=15_552_000)


@lru_cache
def get_settings() -> Settings:
    return Settings()

