from typing import Literal

from pydantic import BaseModel, Field

SourceSort = Literal["seeders", "size", "resolution", "source", "title"]
SortOrder = Literal["asc", "desc"]


class ReleaseCharacteristics(BaseModel):
    resolution: str | None = None
    source: str | None = None
    codec: str | None = None
    hdr: bool = False
    hdr_format: str | None = None
    audio: str | None = None
    language: str | None = None
    release_type: str | None = None


class SourceRelease(ReleaseCharacteristics):
    id: str
    title: str
    indexer: str
    size_bytes: int = Field(ge=0)
    seeders: int | None = Field(default=None, ge=0)
    peers: int | None = Field(default=None, ge=0)
    published_at: str | None = None
    season_number: int | None = Field(default=None, ge=1, le=100)
    protocol: Literal["torrent"] = "torrent"


class SourceResults(BaseModel):
    media_id: int
    media_kind: Literal["movie", "series"]
    query: str
    items: list[SourceRelease]
    total: int


class IndexerSummary(BaseModel):
    id: int
    name: str
    enabled: bool
    protocol: str | None = None
    privacy: str | None = None
