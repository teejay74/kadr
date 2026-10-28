from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.media import EpisodeSummary, MediaKind

PlaybackState = Literal["idle", "probing", "processing", "ready", "failed"]
PlaybackMode = Literal["compatible", "audio_only", "audio_track"]
PlaybackStrategy = Literal["remux", "audio_transcode", "transcode"]
PlaybackResolutionState = Literal[
    "ready",
    "buffering",
    "source_required",
    "unavailable",
]
PlaybackSource = Literal["library", "torrent"]
PlaybackTrackKind = Literal["audio", "subtitle"]
PlaybackTrackDelivery = Literal[
    "native_or_compatible",
    "external_webvtt",
    "burn_in_required",
    "unsupported",
]


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
    track_id: str | None = None


class PlaybackTrack(BaseModel):
    id: str
    preference_key: str
    stream_index: int = Field(ge=0)
    kind: PlaybackTrackKind
    language: str | None = None
    codec: str
    title: str | None = None
    is_default: bool = False
    is_forced: bool = False
    is_hearing_impaired: bool = False
    channels: int | None = Field(default=None, ge=1)
    channel_layout: str | None = None
    delivery: PlaybackTrackDelivery


class PlaybackTrackList(BaseModel):
    source: PlaybackSource
    source_id: str
    file_id: int | None = Field(default=None, ge=0)
    audio_tracks: list[PlaybackTrack] = Field(default_factory=list)
    subtitle_tracks: list[PlaybackTrack] = Field(default_factory=list)
    selected_audio_track_id: str | None = None
    selected_subtitle_track_id: str | None = None
    subtitles_enabled: bool = False


class PlaybackTrackPreferenceRequest(BaseModel):
    profile_key: str = Field(default="default", min_length=1, max_length=64)
    audio_track_id: str | None = Field(default=None, min_length=1, max_length=64)
    subtitle_track_id: str | None = Field(default=None, min_length=1, max_length=64)
    subtitles_enabled: bool = False

    @model_validator(mode="after")
    def validate_subtitle_selection(self) -> "PlaybackTrackPreferenceRequest":
        if self.subtitles_enabled and self.subtitle_track_id is None:
            raise ValueError("subtitle_track_id is required when subtitles are enabled")
        return self


class PlaybackSubtitlePreparation(BaseModel):
    track_id: str
    stream_url: str
