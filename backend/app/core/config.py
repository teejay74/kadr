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
    prowlarr_base_url: str = "http://prowlarr:9696"
    prowlarr_api_key: SecretStr | None = None
    prowlarr_timeout_seconds: float = Field(default=30, gt=0, le=120)
    prowlarr_search_limit: int = Field(default=100, ge=1, le=500)
    qbittorrent_base_url: str = "http://qbittorrent:8080"
    qbittorrent_username: str = "kadr"
    qbittorrent_password: SecretStr | None = None
    qbittorrent_timeout_seconds: float = Field(default=15, gt=0, le=60)
    torrent_save_path: str = "/downloads/cache"
    torrent_storage_root: str = "/downloads"
    min_free_space_gb: float = Field(default=200, ge=0)
    max_active_torrents: int = Field(default=3, ge=1, le=20)


@lru_cache
def get_settings() -> Settings:
    return Settings()
