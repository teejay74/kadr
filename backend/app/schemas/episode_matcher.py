from typing import Literal

from pydantic import BaseModel, Field, model_validator

MatchConfidence = Literal["exact", "probable", "ambiguous"]


class EpisodeMatchIdentity(BaseModel):
    season_number: int = Field(ge=0, le=100)
    episode_number: int = Field(ge=1, le=10_000)
    catalog_episode_id: int | None = Field(default=None, gt=0)
    name: str = ""
    runtime_minutes: int | None = Field(default=None, ge=1)


class EpisodeMatchFile(BaseModel):
    file_id: int = Field(ge=0)
    file_path: str
    confidence: MatchConfidence
    episodes: list[EpisodeMatchIdentity] = Field(default_factory=list)
    alternatives: list[EpisodeMatchIdentity] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    confirmed: bool = False
    confirmation: Literal["automatic", "manual"] | None = None
    unsafe: bool = False
    duration_seconds: int | None = Field(default=None, ge=1)


class EpisodeMatchReport(BaseModel):
    task_id: str
    metadata_available: bool
    files: list[EpisodeMatchFile] = Field(default_factory=list)
    requires_confirmation: bool


class EpisodeMatchSelection(BaseModel):
    file_id: int = Field(ge=0)
    episodes: list[EpisodeMatchIdentity] = Field(min_length=1, max_length=20)
    segment_index: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def unique_episodes(self) -> "EpisodeMatchSelection":
        identities = {
            (episode.season_number, episode.episode_number)
            for episode in self.episodes
        }
        if len(identities) != len(self.episodes):
            raise ValueError("A file mapping cannot contain duplicate episodes")
        return self


class EpisodeMatchConfirmationRequest(BaseModel):
    mappings: list[EpisodeMatchSelection] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_files(self) -> "EpisodeMatchConfirmationRequest":
        file_ids = [mapping.file_id for mapping in self.mappings]
        if len(file_ids) != len(set(file_ids)):
            raise ValueError("Each file can appear only once in a confirmation")
        return self
