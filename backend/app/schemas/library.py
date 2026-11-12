from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.media import MediaKind


class MediaSnapshot(BaseModel):
    media_id: int = Field(gt=0)
    media_kind: MediaKind
    title: str = Field(min_length=1, max_length=512)
    original_title: str = Field(default="", max_length=512)
    poster_url: str | None = Field(default=None, max_length=1024)
    backdrop_url: str | None = Field(default=None, max_length=1024)


class EpisodeIdentity(BaseModel):
    id: str
    media_id: int = Field(gt=0)
    season_number: int = Field(ge=0, le=100)
    episode_number: int = Field(ge=1, le=10_000)
    catalog_episode_id: int | None = Field(default=None, gt=0)


class EpisodeIdentityRequest(BaseModel):
    season_number: int | None = Field(default=None, ge=0, le=100)
    episode_number: int | None = Field(default=None, ge=1, le=10_000)
    catalog_episode_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_episode_identity(self) -> "EpisodeIdentityRequest":
        if (self.season_number is None) != (self.episode_number is None):
            raise ValueError("season_number and episode_number must be provided together")
        return self


class SaveLibraryItemRequest(MediaSnapshot, EpisodeIdentityRequest):
    task_id: str = Field(min_length=36, max_length=36)
    file_id: int | None = Field(default=None, ge=0)


class LibraryItemResponse(MediaSnapshot):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    file_id: int | None = None
    episode: EpisodeIdentity | None = None
    size_bytes: int
    created_at: datetime
    stream_url: str


class FavoriteRequest(MediaSnapshot):
    pass


class FavoriteResponse(MediaSnapshot):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime


class HistorySnapshot(EpisodeIdentityRequest):
    media_kind: MediaKind
    profile_key: str = Field(default="default", min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=512)
    poster_url: str | None = Field(default=None, max_length=1024)
    position_seconds: int = Field(ge=0, le=86_400)
    duration_seconds: int = Field(ge=0, le=86_400)
    completed: bool = False


class EpisodePlaybackProgress(BaseModel):
    duration_ms: int = Field(gt=0, le=86_400_000)
    played_ranges_ms: list[tuple[int, int]] = Field(max_length=256)

    @model_validator(mode="after")
    def validate_ranges(self) -> "EpisodePlaybackProgress":
        if any(
            not 0 <= start < end <= self.duration_ms
            for start, end in self.played_ranges_ms
        ):
            raise ValueError("Played ranges must be within the playback duration")
        return self


class HistoryUpdateRequest(HistorySnapshot):
    playback: EpisodePlaybackProgress | None = None

    @model_validator(mode="after")
    def validate_playback_episode(self) -> "HistoryUpdateRequest":
        if self.playback is not None and (
            self.media_kind != "series" or self.episode_number is None
        ):
            raise ValueError("Played ranges require a series episode")
        return self


class HistoryResponse(HistorySnapshot):
    model_config = ConfigDict(from_attributes=True)

    id: str
    media_id: int
    episode: EpisodeIdentity | None = None
    updated_at: datetime


class CacheCleanupResponse(BaseModel):
    removed_tasks: int
    reclaimed_bytes: int


class CacheFileDeletionResponse(BaseModel):
    task_id: str
    file_id: int = Field(ge=0)
    reclaimed_bytes: int = Field(ge=0)
    selected_file_cleared: bool


class CacheTaskDeletionResponse(BaseModel):
    task_id: str
    reclaimed_bytes: int = Field(ge=0)


class StorageResponse(BaseModel):
    library_bytes: int
    library_items: int
    cache_bytes: int
    cache_tasks: int
    free_bytes: int
