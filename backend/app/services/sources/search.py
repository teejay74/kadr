from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol

from app.schemas.media import MediaDetails, MediaKind
from app.schemas.sources import (
    IndexerSummary,
    SortOrder,
    SourceRelease,
    SourceResults,
    SourceSort,
)
from app.services.sources.release_parser import parse_release_seasons, parse_release_title


class MediaCatalog(Protocol):
    async def details(self, kind: MediaKind, media_id: int) -> MediaDetails: ...


class IndexerProvider(Protocol):
    async def search(self, query: str, media_kind: str) -> list[dict[str, Any]]: ...

    async def list_indexers(self) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class ResolvedSource:
    release: SourceRelease
    uri: str
    info_hash: str | None


class SourceSearchService:
    def __init__(
        self,
        catalog: MediaCatalog,
        provider: IndexerProvider,
    ) -> None:
        self._catalog = catalog
        self._provider = provider

    async def search(
        self,
        media_id: int,
        media_kind: MediaKind,
        sort: SourceSort,
        order: SortOrder,
        season_number: int | None = None,
    ) -> SourceResults:
        query, raw_items = await self._search_raw(media_id, media_kind, season_number)
        items = [
            release
            for payload in raw_items
            if (release := self._normalize(payload, season_number)) is not None
        ]
        items.sort(key=self._sort_key(sort), reverse=order == "desc")
        return SourceResults(
            media_id=media_id,
            media_kind=media_kind,
            query=query,
            items=items,
            total=len(items),
        )

    async def resolve(
        self,
        media_id: int,
        media_kind: MediaKind,
        source_id: str,
        season_number: int | None = None,
    ) -> ResolvedSource | None:
        _, raw_items = await self._search_raw(media_id, media_kind, season_number)
        for payload in raw_items:
            release = self._normalize(payload, season_number)
            if release is None or release.id != source_id:
                continue
            uri = self._optional_text(payload.get("magnetUrl")) or self._optional_text(
                payload.get("downloadUrl")
            )
            if uri is None:
                return None
            return ResolvedSource(
                release=release,
                uri=uri,
                info_hash=self._optional_text(payload.get("infoHash")),
            )
        return None

    async def _search_raw(
        self,
        media_id: int,
        media_kind: MediaKind,
        season_number: int | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        media = await self._catalog.details(media_kind, media_id)
        title = media.title or media.original_title
        query = self._query(title, media.year, season_number)
        raw_items = await self._provider.search(query, media_kind)
        if not raw_items and media.original_title and media.original_title != title:
            query = self._query(media.original_title, media.year, season_number)
            raw_items = await self._provider.search(query, media_kind)
        return query, raw_items

    @staticmethod
    def _query(title: str, year: int | None, season_number: int | None = None) -> str:
        parts = [title]
        if year:
            parts.append(str(year))
        if season_number is not None:
            parts.append(f"S{season_number:02d}")
        return " ".join(parts)

    async def indexers(self) -> list[IndexerSummary]:
        raw_items = await self._provider.list_indexers()
        return [
            IndexerSummary(
                id=int(item.get("id") or 0),
                name=str(item.get("name") or item.get("implementationName") or "Indexer"),
                enabled=bool(item.get("enable", False)),
                protocol=self._optional_text(item.get("protocol")),
                privacy=self._optional_text(item.get("privacy")),
            )
            for item in raw_items
            if item.get("id") is not None
        ]

    def _normalize(
        self,
        payload: dict[str, Any],
        season_number: int | None = None,
    ) -> SourceRelease | None:
        if str(payload.get("protocol") or "").lower() != "torrent":
            return None
        title = self._optional_text(payload.get("title"))
        if title is None:
            return None
        indexer = str(payload.get("indexer") or "Unknown indexer")
        size = max(self._integer(payload.get("size"), default=0), 0)
        identity = str(
            payload.get("guid") or payload.get("infoHash") or f"{indexer}:{title}:{size}"
        )
        parsed = parse_release_title(title)
        return SourceRelease(
            id=hashlib.sha256(identity.encode()).hexdigest()[:24],
            title=title,
            indexer=indexer,
            size_bytes=size,
            seeders=self._optional_non_negative_integer(payload.get("seeders")),
            peers=self._optional_non_negative_integer(payload.get("leechers")),
            published_at=self._optional_text(payload.get("publishDate")),
            season_number=season_number,
            season_numbers=parse_release_seasons(title),
            **parsed.model_dump(),
        )

    @staticmethod
    def _sort_key(sort: SourceSort):
        resolution_rank = {"2160p": 4, "1080p": 3, "720p": 2, "480p": 1}
        source_rank = {"BluRay": 5, "WEB-DL": 4, "WEBRip": 3, "HDTV": 2, "DVDRip": 1, "CAM": 0}
        if sort == "seeders":
            return lambda item: item.seeders if item.seeders is not None else -1
        if sort == "size":
            return lambda item: item.size_bytes
        if sort == "resolution":
            return lambda item: resolution_rank.get(item.resolution or "", -1)
        if sort == "source":
            return lambda item: source_rank.get(item.source or "", -1)
        return lambda item: item.title.casefold()

    @staticmethod
    def _integer(value: object, *, default: int) -> int:
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default

    @classmethod
    def _optional_non_negative_integer(cls, value: object) -> int | None:
        if value is None:
            return None
        return max(cls._integer(value, default=0), 0)

    @staticmethod
    def _optional_text(value: object) -> str | None:
        return value if isinstance(value, str) and value else None
