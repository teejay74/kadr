from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.media import MediaKind


class AddTorrentRequest(BaseModel):
    media_kind: MediaKind
    source_id: str = Field(min_length=24, max_length=24, pattern=r"^[0-9a-f]+$")
    season_number: int | None = Field(default=None, ge=1, le=100)


class SelectTorrentFileRequest(BaseModel):
    file_id: int = Field(ge=0)
    season_number: int | None = Field(default=None, ge=0, le=100)
    episode_number: int | None = Field(default=None, ge=1, le=10_000)
    catalog_episode_id: int | None = Field(default=None, gt=0)
    variant_label: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_episode_identity(self) -> "SelectTorrentFileRequest":
        if (self.season_number is None) != (self.episode_number is None):
            raise ValueError("season_number and episode_number must be provided together")
        return self


class EpisodeFileBindingResponse(BaseModel):
    id: str
    episode_id: str
    media_id: int = Field(gt=0)
    season_number: int = Field(ge=0)
    episode_number: int = Field(ge=1)
    catalog_episode_id: int | None = Field(default=None, gt=0)
    file_variant_id: str
    file_id: int = Field(ge=0)
    variant_label: str | None = None


class PrefetchTorrentFilesRequest(BaseModel):
    file_ids: list[int] = Field(default_factory=list, max_length=100)


class TorrentFile(BaseModel):
    id: int = Field(ge=0)
    name: str
    size_bytes: int = Field(ge=0)
    progress: float = Field(ge=0, le=1)
    priority: int = Field(ge=0)
    is_video: bool


class TorrentStatus(BaseModel):
    id: str
    media_id: int
    media_kind: MediaKind
    name: str
    state: str
    progress: float = Field(ge=0, le=1)
    downloaded_bytes: int = Field(ge=0)
    total_size_bytes: int = Field(ge=0)
    download_speed_bytes: int = Field(ge=0)
    upload_speed_bytes: int = Field(ge=0)
    peers: int = Field(ge=0)
    seeds: int = Field(ge=0)
    eta_seconds: int | None = Field(default=None, ge=0)
    selected_file_id: int | None = None
    selected_file_path: str | None = None
    can_start: bool
    can_stop: bool


class StreamReadiness(BaseModel):
    ready: bool
    buffer_progress: float = Field(ge=0, le=1)


TorrentAction = Literal["start", "stop"]
