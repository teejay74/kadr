from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.media import EpisodeSummary, MediaKind

PlaybackState = Literal["idle", "probing", "processing", "ready", "failed"]
PlaybackMode = Literal["compatible", "audio_only"]
PlaybackStrategy = Literal["remux", "audio_transcode", "transcode"]
PlaybackResolutionState = Literal[
    "ready",
    "buffering",
    "source_required",
    "unavailable",
]
PlaybackSource = Literal["library", "torrent"]


class PlaybackResolveRequest(BaseModel):
    media_kind: MediaKind
    media_id: int = Field(gt=0)
    season_number: int | None = Field(default=None, ge=0, le=100)
    episode_number: int | None = Field(default=None, ge=1, le=10_000)
    catalog_episode_id: int | None = Field(default=None, gt=0)
    profile_key: str = Field(default="default", min_length=1, max_length=64)
    preferred_task_id: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_identity(self) -> "PlaybackResolveRequest":
        if (self.season_number is None) != (self.episode_number is None):
            raise ValueError("season_number and episode_number must be provided together")
        if self.media_kind == "movie" and self.season_number is not None:
            raise ValueError("Episode identity can only be assigned to a series")
        return self


class PlaybackResolution(BaseModel):
    status: PlaybackResolutionState
    source: PlaybackSource | None = None
    stream_url: str | None = None
    task_id: str | None = None
    file_id: int | None = Field(default=None, ge=0)
    library_item_id: str | None = None
    resume_position_seconds: int = Field(default=0, ge=0)
    buffer_progress: float = Field(default=0, ge=0, le=1)
    download_progress: float = Field(default=0, ge=0, le=1)
    download_state: str | None = None
    download_speed_bytes: int = Field(default=0, ge=0)
    message: str | None = None


class NextEpisodeRequest(BaseModel):
    media_id: int = Field(gt=0)
    season_number: int = Field(ge=0, le=100)
    episode_number: int = Field(ge=1, le=10_000)
    catalog_episode_id: int | None = Field(default=None, gt=0)
    profile_key: str = Field(default="default", min_length=1, max_length=64)
    current_task_id: str | None = Field(default=None, min_length=1, max_length=64)
    current_file_id: int | None = Field(default=None, ge=0)


NextEpisodeState = Literal[
    "ready",
    "buffering",
    "source_required",
    "unavailable",
    "end",
]


class NextEpisodeResolution(BaseModel):
    status: NextEpisodeState
    episode: EpisodeSummary | None = None
    playback: PlaybackResolution | None = None
    prefetched: bool = False
    combined_file: bool = False
    message: str | None = None


class PlaybackPreparation(BaseModel):
    mode: PlaybackMode = "compatible"
    state: PlaybackState
    progress: float = Field(ge=0, le=1)
    strategy: PlaybackStrategy | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    message: str | None = None
    stream_url: str | None = None
