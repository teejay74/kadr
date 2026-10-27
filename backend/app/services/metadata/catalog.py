from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Literal, Protocol

from app.core.config import Settings
from app.repositories.metadata_cache import MetadataCacheRepository
from app.schemas.media import (
    CastMember,
    EpisodeSummary,
    Genre,
    MediaCard,
    MediaDetails,
    MediaKind,
    MediaPage,
    SeasonDetails,
    SeasonSummary,
)
from app.services.metadata.exceptions import MetadataUnavailableError

logger = logging.getLogger(__name__)
SortMode = Literal["popular", "rating", "newest"]


class MetadataProvider(Protocol):
    async def get(
        self,
        path: str,
        params: dict[str, str | int | bool],
    ) -> dict[str, Any]: ...


class CatalogService:
    def __init__(
        self,
        client: MetadataProvider,
        cache: MetadataCacheRepository,
        settings: Settings,
    ) -> None:
        self._client = client
        self._cache = cache
        self._settings = settings

    async def list_media(
        self,
        kind: MediaKind,
        *,
        page: int,
        sort: SortMode,
        genre: int | None,
        year: int | None,
    ) -> MediaPage:
        date_field = "primary_release_date" if kind == "movie" else "first_air_date"
        sort_by = {
            "popular": "popularity.desc",
            "rating": "vote_average.desc",
            "newest": f"{date_field}.desc",
        }[sort]
        params: dict[str, str | int | bool] = {
            "page": page,
            "sort_by": sort_by,
            "include_adult": False,
            "region": self._settings.tmdb_region,
        }
        if sort == "rating":
            params["vote_count.gte"] = 100
        if genre is not None:
            params["with_genres"] = genre
        if year is not None:
            params["primary_release_year" if kind == "movie" else "first_air_date_year"] = year
        tmdb_kind = "movie" if kind == "movie" else "tv"
        payload = await self._request(f"/discover/{tmdb_kind}", params)
        return self._page(payload, kind)

    async def search(
        self,
        kind: MediaKind,
        query: str,
        *,
        page: int,
        year: int | None,
    ) -> MediaPage:
        params: dict[str, str | int | bool] = {
            "query": query,
            "page": page,
            "include_adult": False,
            "region": self._settings.tmdb_region,
        }
        if year is not None:
            params["year" if kind == "movie" else "first_air_date_year"] = year
        tmdb_kind = "movie" if kind == "movie" else "tv"
        payload = await self._request(f"/search/{tmdb_kind}", params)
        return self._page(payload, kind)

    async def details(self, kind: MediaKind, media_id: int) -> MediaDetails:
        tmdb_kind = "movie" if kind == "movie" else "tv"
        payload = await self._request(
            f"/{tmdb_kind}/{media_id}",
            {"append_to_response": "credits,videos"},
        )
        return self._details(payload, kind)

    async def season(self, media_id: int, season_number: int) -> SeasonDetails:
        payload = await self._request(f"/tv/{media_id}/season/{season_number}", {})
        return self._season(payload, media_id, season_number)

    async def genres(self, kind: MediaKind) -> list[Genre]:
        tmdb_kind = "movie" if kind == "movie" else "tv"
        payload = await self._request(f"/genre/{tmdb_kind}/list", {})
        genres = payload.get("genres")
        return [Genre.model_validate(item) for item in genres] if isinstance(genres, list) else []

    async def _request(
        self,
        path: str,
        params: dict[str, str | int | bool],
    ) -> dict[str, Any]:
        cache_material = json.dumps(
            [path, self._settings.tmdb_language, params],
            sort_keys=True,
            separators=(",", ":"),
        )
        key = hashlib.sha256(cache_material.encode()).hexdigest()
        cached = await self._cache.get(key)
        if cached is not None:
            return cached
        try:
            payload = await self._client.get(path, params)
        except MetadataUnavailableError:
            stale = await self._cache.get(key, allow_expired=True)
            if stale is not None:
                logger.warning("Serving stale TMDB cache for %s", path)
                return stale
            raise
        await self._cache.set(key, payload, self._settings.metadata_cache_ttl_seconds)
        return payload

    def _page(self, payload: dict[str, Any], kind: MediaKind) -> MediaPage:
        results = payload.get("results")
        items = [self._card(item, kind) for item in results] if isinstance(results, list) else []
        return MediaPage(
            items=items,
            page=int(payload.get("page") or 1),
            total_pages=min(int(payload.get("total_pages") or 0), 500),
            total_results=int(payload.get("total_results") or 0),
        )

    def _card(self, payload: dict[str, Any], kind: MediaKind) -> MediaCard:
        title_key = "title" if kind == "movie" else "name"
        original_key = "original_title" if kind == "movie" else "original_name"
        date_key = "release_date" if kind == "movie" else "first_air_date"
        release_date = self._optional_text(payload.get(date_key))
        return MediaCard(
            id=int(payload["id"]),
            kind=kind,
            title=str(payload.get(title_key) or payload.get(original_key) or "Без названия"),
            original_title=str(payload.get(original_key) or payload.get(title_key) or ""),
            overview=str(payload.get("overview") or ""),
            release_date=release_date,
            year=self._year(release_date),
            poster_url=self._image(payload.get("poster_path"), "w500"),
            backdrop_url=self._image(payload.get("backdrop_path"), "w1280"),
            rating=float(payload.get("vote_average") or 0),
            popularity=float(payload.get("popularity") or 0),
            genre_ids=[int(item) for item in payload.get("genre_ids", [])],
        )

    def _details(self, payload: dict[str, Any], kind: MediaKind) -> MediaDetails:
        card = self._card(payload, kind)
        genres = [Genre.model_validate(item) for item in payload.get("genres", [])]
        credits = payload.get("credits") or {}
        cast = [
            CastMember(
                id=int(item["id"]),
                name=str(item.get("name") or ""),
                character=self._optional_text(item.get("character")),
                profile_url=self._image(item.get("profile_path"), "w185"),
            )
            for item in credits.get("cast", [])[:12]
        ]
        videos = (payload.get("videos") or {}).get("results", [])
        trailer = next(
            (
                item
                for item in videos
                if item.get("site") == "YouTube"
                and item.get("type") == "Trailer"
                and item.get("key")
            ),
            None,
        )
        seasons = [
            SeasonSummary(
                id=int(item["id"]),
                number=int(item.get("season_number") or 0),
                name=str(item.get("name") or ""),
                episode_count=int(item.get("episode_count") or 0),
                air_date=self._optional_text(item.get("air_date")),
                poster_url=self._image(item.get("poster_path"), "w342"),
            )
            for item in payload.get("seasons", [])
        ]
        runtimes = payload.get("episode_run_time") or []
        runtime = payload.get("runtime") if kind == "movie" else (runtimes[0] if runtimes else None)
        return MediaDetails(
            **card.model_dump(),
            genres=genres,
            runtime_minutes=int(runtime) if runtime else None,
            status=self._optional_text(payload.get("status")),
            tagline=self._optional_text(payload.get("tagline")),
            cast=cast,
            trailer_url=f"https://www.youtube.com/watch?v={trailer['key']}" if trailer else None,
            seasons=seasons,
            season_count=(
                int(payload["number_of_seasons"])
                if payload.get("number_of_seasons")
                else None
            ),
            episode_count=(
                int(payload["number_of_episodes"])
                if payload.get("number_of_episodes")
                else None
            ),
        )

    def _season(
        self,
        payload: dict[str, Any],
        media_id: int,
        season_number: int,
    ) -> SeasonDetails:
        episodes = [
            EpisodeSummary(
                id=int(item["id"]),
                season_number=int(item.get("season_number") or season_number),
                number=int(item.get("episode_number") or 0),
                name=str(item.get("name") or f"Серия {item.get('episode_number') or 0}"),
                overview=str(item.get("overview") or ""),
                air_date=self._optional_text(item.get("air_date")),
                runtime_minutes=(int(item["runtime"]) if item.get("runtime") else None),
                still_url=self._image(item.get("still_path"), "w500"),
                rating=float(item.get("vote_average") or 0),
            )
            for item in payload.get("episodes", [])
            if isinstance(item, dict) and item.get("id") is not None
        ]
        return SeasonDetails(
            id=int(payload.get("id") or 0),
            series_id=media_id,
            number=int(payload.get("season_number") or season_number),
            name=str(payload.get("name") or f"Сезон {season_number}"),
            overview=str(payload.get("overview") or ""),
            air_date=self._optional_text(payload.get("air_date")),
            poster_url=self._image(payload.get("poster_path"), "w342"),
            episodes=episodes,
        )

    def _image(self, path: object, size: str) -> str | None:
        if not isinstance(path, str):
            return None
        return f"{self._settings.tmdb_image_base_url}/{size}{path}"

    @staticmethod
    def _optional_text(value: object) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _year(value: str | None) -> int | None:
        return int(value[:4]) if value and len(value) >= 4 and value[:4].isdigit() else None
