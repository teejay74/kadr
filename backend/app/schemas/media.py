from typing import Literal

from pydantic import BaseModel, Field

MediaKind = Literal["movie", "series"]


class Genre(BaseModel):
    id: int
    name: str


class CastMember(BaseModel):
    id: int
    name: str
    character: str | None = None
    profile_url: str | None = None


class SeasonSummary(BaseModel):
    id: int
    number: int
    name: str
    episode_count: int
    air_date: str | None = None
    poster_url: str | None = None


class MediaCard(BaseModel):
    id: int
    kind: MediaKind
    title: str
    original_title: str
    overview: str
    release_date: str | None = None
    year: int | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None
    rating: float = 0
    popularity: float = 0
    genre_ids: list[int] = Field(default_factory=list)


class MediaPage(BaseModel):
    items: list[MediaCard]
    page: int
    total_pages: int
    total_results: int


class MediaDetails(MediaCard):
    genres: list[Genre] = Field(default_factory=list)
    runtime_minutes: int | None = None
    status: str | None = None
    tagline: str | None = None
    cast: list[CastMember] = Field(default_factory=list)
    trailer_url: str | None = None
    seasons: list[SeasonSummary] = Field(default_factory=list)
    season_count: int | None = None
    episode_count: int | None = None
