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
    library_root: str = "/library"
    min_free_space_gb: float = Field(default=200, ge=0)
    max_active_torrents: int = Field(default=3, ge=1, le=20)
    max_active_streams: int = Field(default=2, ge=1, le=10)
    max_range_requests_per_stream: int = Field(default=32, ge=2, le=64)
    stream_start_buffer_mb: int = Field(default=32, ge=1, le=512)
    stream_read_timeout_seconds: float = Field(default=30, gt=0, le=300)
    stream_poll_interval_seconds: float = Field(default=0.5, gt=0, le=5)
    stream_chunk_size_kb: int = Field(default=1024, ge=64, le=8192)
    playback_cache_root: str = "/playback"
    playback_min_free_space_gb: float = Field(default=5, ge=0)
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    max_active_transcodes: int = Field(default=1, ge=1, le=2)
    transcode_video_threads: int = Field(default=2, ge=1, le=8)
    transcode_video_preset: str = "veryfast"
    transcode_video_crf: int = Field(default=23, ge=16, le=32)
    transcode_max_width: int = Field(default=1920, ge=320, le=3840)
    transcode_max_height: int = Field(default=1080, ge=240, le=2160)
    transcode_audio_bitrate: str = "192k"
    cache_ttl_hours: int = Field(default=24, ge=1, le=8760)
    cache_cleanup_interval_minutes: int = Field(default=60, ge=5, le=1440)


@lru_cache
def get_settings() -> Settings:
    return Settings()
