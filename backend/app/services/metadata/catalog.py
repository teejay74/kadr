from __future__ import annotations

import hashlib
import json
import logging
import re
import zlib
from datetime import UTC, datetime, timedelta
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
from app.services.metadata.exceptions import (
    MetadataError,
    MetadataNotConfiguredError,
    MetadataNotFoundError,
    MetadataUnavailableError,
)

logger = logging.getLogger(__name__)
SortMode = Literal["popular", "rating", "newest"]
AgeRating = Literal["0+", "6+", "12+", "16+", "18+"]
KINOPOISK_ID_OFFSET = 1_500_000_000
MAX_PUBLIC_MEDIA_ID = 2_147_483_647


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
        kinopoisk_client: MetadataProvider | None = None,
    ) -> None:
        self._client = client
        self._cache = cache
        self._settings = settings
        self._kinopoisk_client = kinopoisk_client

    async def list_media(
        self,
        kind: MediaKind,
        *,
        page: int,
        sort: SortMode,
        genre: int | None,
        year: int | None,
        age_rating: AgeRating | None = None,
        released_within_days: int | None = None,
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
        if age_rating is not None and kind == "movie":
            params["certification_country"] = "RU"
            params["certification"] = age_rating
        tmdb_kind = "movie" if kind == "movie" else "tv"
        path = f"/discover/{tmdb_kind}"
        previous_window: dict[str, str | int | bool] | None = None
        if released_within_days is not None:
            today = datetime.now(UTC).date()
            date_prefix = "release_date" if kind == "movie" else "first_air_date"
            start = today - timedelta(days=released_within_days)
            params[f"{date_prefix}.gte"] = str(start)
            params[f"{date_prefix}.lte"] = str(today)
            if kind == "movie":
                # TMDB release type 4 is digital. Combined with RU region this
                # excludes theatrical-only premieres from the new-release rail.
                params["with_release_type"] = 4
            previous_window = {
                **params,
                f"{date_prefix}.gte": str(start - timedelta(days=1)),
                f"{date_prefix}.lte": str(today - timedelta(days=1)),
            }
        try:
            payload = await self._request(path, params)
        except MetadataUnavailableError:
            if previous_window is None:
                raise
            payload = await self._cache.get(
                self._cache_key("tmdb", path, previous_window, self._settings.tmdb_language),
                allow_expired=True,
            )
            if payload is None:
                raise
            logger.warning("Serving previous TMDB release window for %s", path)
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
        try:
            payload = await self._request(f"/search/{tmdb_kind}", params)
            page_result = self._page(payload, kind)
        except MetadataUnavailableError:
            if page != 1 or self._kinopoisk_client is None:
                raise
            logger.warning("TMDB search unavailable; using Kinopoisk fallback")
            page_result = MediaPage(items=[], page=1, total_pages=0, total_results=0)
        if page != 1 or self._kinopoisk_client is None:
            return page_result
        return await self._enrich_search(page_result, kind, query, year, tmdb_kind)

    async def _enrich_search(
        self,
        primary: MediaPage,
        kind: MediaKind,
        query: str,
        year: int | None,
        tmdb_kind: str,
    ) -> MediaPage:
        try:
            payload = await self._kinopoisk_request(
                "/api/v2.1/films/search-by-keyword",
                {"keyword": query, "page": 1},
            )
        except MetadataNotConfiguredError:
            return primary
        except MetadataError:
            logger.warning("Kinopoisk search fallback failed", exc_info=True)
            return primary

        raw_films = payload.get("films")
        if not isinstance(raw_films, list):
            return primary

        items = list(primary.items)
        known_ids = {item.id for item in items}
        searched = {query.casefold()}
        alias_searches = 0
        candidates = [
            item
            for item in raw_films
            if isinstance(item, dict)
            and self._kinopoisk_matches_kind(item, kind)
            and self._kinopoisk_matches_query(item, query)
        ][: self._settings.kinopoisk_search_alias_limit]
        for candidate in candidates:
            titles = self._kinopoisk_titles(candidate)
            candidate_year = year or self._int_year(candidate.get("year"))
            matched_tmdb = False
            for title in titles:
                normalized = title.casefold()
                if (
                    normalized in searched
                    or alias_searches >= self._settings.kinopoisk_search_alias_limit
                ):
                    continue
                searched.add(normalized)
                alias_searches += 1
                params: dict[str, str | int | bool] = {
                    "query": title,
                    "page": 1,
                    "include_adult": False,
                    "region": self._settings.tmdb_region,
                }
                if candidate_year is not None:
                    params["year" if kind == "movie" else "first_air_date_year"] = candidate_year
                try:
                    extra = self._page(
                        await self._request(f"/search/{tmdb_kind}", params),
                        kind,
                    )
                except MetadataError:
                    extra = MediaPage(items=[], page=1, total_pages=0, total_results=0)
                for item in extra.items:
                    if self._media_matches_title(item, title) and item.id not in known_ids:
                        known_ids.add(item.id)
                        items.append(item)
                        matched_tmdb = True
            if not matched_tmdb:
                fallback = self._kinopoisk_card(candidate, kind)
                if fallback is not None and fallback.id not in known_ids:
                    duplicate = any(self._same_catalogue_title(item, fallback) for item in items)
                    if not duplicate:
                        known_ids.add(fallback.id)
                        items.insert(0, fallback)
        items = items[:20]
        return MediaPage(
            items=items,
            page=primary.page,
            total_pages=max(primary.total_pages, 1 if items else 0),
            total_results=max(primary.total_results, len(items)),
        )

    async def details(
        self,
        kind: MediaKind,
        media_id: int,
        *,
        fallback_title: str | None = None,
        fallback_year: int | None = None,
        include_ratings: bool = False,
        allow_partial: bool = False,
    ) -> MediaDetails:
        if self._is_kinopoisk_id(media_id):
            return await self._kinopoisk_details(kind, media_id)
        tmdb_kind = "movie" if kind == "movie" else "tv"
        try:
            payload = await self._request(
                f"/{tmdb_kind}/{media_id}",
                {"append_to_response": "credits,videos"},
            )
        except MetadataUnavailableError:
            if fallback_title is not None and self._kinopoisk_client is not None:
                try:
                    return await self._kinopoisk_details_by_title(
                        kind, fallback_title, fallback_year
                    )
                except MetadataError as fallback_error:
                    logger.warning(
                        "Kinopoisk details fallback failed for TMDB media %s (%s)",
                        media_id,
                        type(fallback_error).__name__,
                    )
            if not allow_partial:
                raise
            cached_item = await self._cache.find_catalogue_item(
                media_id,
                title_key="title" if kind == "movie" else "name",
                date_key="release_date" if kind == "movie" else "first_air_date",
            )
            if cached_item is not None:
                logger.warning(
                    "Serving partial TMDB details from catalogue for %s/%s", kind, media_id
                )
                return MediaDetails(
                    **self._card(cached_item, kind).model_dump(), metadata_partial=True
                )
            raise
        details = self._details(payload, kind)
        if include_ratings and kind == "movie":
            await self._enrich_movie_ratings(details, payload.get("imdb_id"))
        return details

    async def _enrich_movie_ratings(self, details: MediaDetails, imdb_id: object) -> None:
        if (
            self._kinopoisk_client is None
            or not self._settings.kinopoisk_api_key
            or not isinstance(imdb_id, str)
            or re.fullmatch(r"tt[0-9]+", imdb_id) is None
        ):
            return
        try:
            payload = await self._kinopoisk_request("/api/v2.2/films", {"imdbId": imdb_id})
        except MetadataError as error:
            logger.warning(
                "Kinopoisk ratings unavailable for movie %s (%s)", details.id, type(error).__name__
            )
            return
        items = payload.get("items")
        if not isinstance(items, list):
            return
        matches = [
            item
            for item in items
            if isinstance(item, dict)
            and item.get("imdbId") == imdb_id
            and self._kinopoisk_matches_kind(item, "movie")
        ]
        if len(matches) == 1:
            details.imdb_rating = self._external_rating(matches[0].get("ratingImdb"))
            details.kinopoisk_rating = self._external_rating(matches[0].get("ratingKinopoisk"))

    async def _kinopoisk_details_by_title(
        self,
        kind: MediaKind,
        title: str,
        year: int | None,
    ) -> MediaDetails:
        payload = await self._kinopoisk_request(
            "/api/v2.1/films/search-by-keyword",
            {"keyword": title, "page": 1},
        )
        raw_films = payload.get("films")
        films = raw_films if isinstance(raw_films, list) else []
        normalized_title = self._normalize_title(title)
        candidates = [
            item
            for item in films
            if isinstance(item, dict)
            and self._kinopoisk_matches_kind(item, kind)
            and any(
                self._normalize_title(candidate_title) == normalized_title
                for candidate_title in self._kinopoisk_titles(item)
            )
        ]
        if year is not None:
            candidates = [
                item
                for item in candidates
                if self._int_year(item.get("year")) == year
                or self._int_year(item.get("startYear")) == year
            ]
        for candidate in candidates:
            card = self._kinopoisk_card(candidate, kind)
            if card is not None:
                logger.warning(
                    "Serving Kinopoisk details fallback for unavailable TMDB title %s",
                    title,
                )
                return await self._kinopoisk_details(kind, card.id)
        raise MetadataNotFoundError("Kinopoisk fallback title was not found")

    async def season(self, media_id: int, season_number: int) -> SeasonDetails:
        if self._is_kinopoisk_id(media_id):
            return await self._kinopoisk_season(media_id, season_number)
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
        return await self._cached_request(
            "tmdb",
            self._client,
            path,
            params,
            self._settings.tmdb_language,
        )

    async def _kinopoisk_request(
        self,
        path: str,
        params: dict[str, str | int | bool],
    ) -> dict[str, Any]:
        if self._kinopoisk_client is None:
            raise MetadataNotFoundError("Kinopoisk metadata provider is unavailable")
        return await self._cached_request("kinopoisk", self._kinopoisk_client, path, params, None)

    async def _cached_request(
        self,
        provider_name: str,
        provider: MetadataProvider,
        path: str,
        params: dict[str, str | int | bool],
        language: str | None,
    ) -> dict[str, Any]:
        key = self._cache_key(provider_name, path, params, language)
        cached = await self._cache.get(key)
        if cached is not None:
            return cached
        try:
            payload = await provider.get(path, params)
        except MetadataUnavailableError:
            stale = await self._cache.get(key, allow_expired=True)
            if stale is not None:
                logger.warning("Serving stale %s cache for %s", provider_name, path)
                return stale
            raise
        await self._cache.set(key, payload, self._settings.metadata_cache_ttl_seconds)
        return payload

    @staticmethod
    def _cache_key(
        provider_name: str,
        path: str,
        params: dict[str, str | int | bool],
        language: str | None,
    ) -> str:
        material = json.dumps(
            [provider_name, path, language, params], sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(material.encode()).hexdigest()

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

    async def _kinopoisk_details(self, kind: MediaKind, media_id: int) -> MediaDetails:
        kinopoisk_id = media_id - KINOPOISK_ID_OFFSET
        payload = await self._kinopoisk_request(f"/api/v2.2/films/{kinopoisk_id}", {})
        if not self._kinopoisk_matches_kind(payload, kind):
            raise MetadataNotFoundError("Media kind does not match Kinopoisk metadata")
        card = self._kinopoisk_card(payload, kind)
        if card is None:
            raise MetadataNotFoundError("Kinopoisk media ID is outside the supported range")

        season_items: list[dict[str, Any]] = []
        if kind == "series":
            season_payload = await self._kinopoisk_request(
                f"/api/v2.2/films/{kinopoisk_id}/seasons",
                {},
            )
            raw_seasons = season_payload.get("items")
            if isinstance(raw_seasons, list):
                season_items = [item for item in raw_seasons if isinstance(item, dict)]

        seasons = [self._kinopoisk_season_summary(media_id, item) for item in season_items]
        genres = [
            Genre(id=self._kinopoisk_genre_id(name), name=name)
            for name in self._kinopoisk_genre_names(payload)
        ]
        runtime = self._int_value(payload.get("filmLength"))
        completed = payload.get("completed") is True
        status = self._optional_text(payload.get("productionStatus"))
        if status is None and completed:
            status = "Завершён"
        elif status is None and kind == "series":
            status = "Продолжается"
        return MediaDetails(
            **card.model_dump(),
            genres=genres,
            runtime_minutes=runtime,
            imdb_rating=(
                self._external_rating(payload.get("ratingImdb")) if kind == "movie" else None
            ),
            kinopoisk_rating=(
                self._external_rating(payload.get("ratingKinopoisk")) if kind == "movie" else None
            ),
            status=status,
            tagline=self._optional_text(payload.get("slogan")),
            cast=[],
            trailer_url=None,
            seasons=seasons,
            season_count=len(seasons) if kind == "series" else None,
            episode_count=(
                sum(len(item.get("episodes") or []) for item in season_items)
                if kind == "series"
                else None
            ),
        )

    async def _kinopoisk_season(
        self,
        media_id: int,
        season_number: int,
    ) -> SeasonDetails:
        kinopoisk_id = media_id - KINOPOISK_ID_OFFSET
        payload = await self._kinopoisk_request(
            f"/api/v2.2/films/{kinopoisk_id}/seasons",
            {},
        )
        raw_seasons = payload.get("items")
        seasons = raw_seasons if isinstance(raw_seasons, list) else []
        season = next(
            (
                item
                for item in seasons
                if isinstance(item, dict) and self._int_value(item.get("number")) == season_number
            ),
            None,
        )
        if season is None:
            raise MetadataNotFoundError("Season was not found")
        raw_episodes = season.get("episodes")
        episode_items = raw_episodes if isinstance(raw_episodes, list) else []
        episodes = [
            EpisodeSummary(
                id=self._stable_id(
                    f"kinopoisk:{kinopoisk_id}:{season_number}:{episode_number}"
                ),
                season_number=season_number,
                number=episode_number,
                name=str(
                    item.get("nameRu")
                    or item.get("nameEn")
                    or f"Серия {episode_number}"
                ),
                overview=str(item.get("synopsis") or ""),
                air_date=self._optional_text(item.get("releaseDate")),
                runtime_minutes=None,
                still_url=None,
                rating=0,
            )
            for item in episode_items
            if isinstance(item, dict)
            and (episode_number := self._int_value(item.get("episodeNumber"))) is not None
        ]
        air_dates = [item.air_date for item in episodes if item.air_date]
        return SeasonDetails(
            id=self._stable_id(f"kinopoisk:{kinopoisk_id}:{season_number}"),
            series_id=media_id,
            number=season_number,
            name=f"Сезон {season_number}",
            overview="",
            air_date=min(air_dates) if air_dates else None,
            poster_url=None,
            episodes=episodes,
        )

    def _kinopoisk_card(
        self,
        payload: dict[str, Any],
        kind: MediaKind,
    ) -> MediaCard | None:
        raw_id = payload.get("kinopoiskId", payload.get("filmId"))
        kinopoisk_id = self._int_value(raw_id)
        if kinopoisk_id is None:
            return None
        public_id = self._encode_kinopoisk_id(kinopoisk_id)
        if public_id is None:
            return None
        titles = self._kinopoisk_titles(payload)
        title = self._optional_text(payload.get("nameRu")) or (
            titles[0] if titles else "Без названия"
        )
        original_title = (
            self._optional_text(payload.get("nameOriginal"))
            or self._optional_text(payload.get("nameEn"))
            or title
        )
        year = self._int_year(payload.get("year")) or self._int_year(payload.get("startYear"))
        genre_names = self._kinopoisk_genre_names(payload)
        return MediaCard(
            id=public_id,
            kind=kind,
            title=title,
            original_title=original_title,
            overview=str(payload.get("description") or payload.get("shortDescription") or ""),
            release_date=None,
            year=year,
            poster_url=(
                self._optional_text(payload.get("posterUrlPreview"))
                or self._optional_text(payload.get("posterUrl"))
            ),
            backdrop_url=self._optional_text(payload.get("coverUrl")),
            rating=self._float_value(
                payload.get("ratingKinopoisk", payload.get("rating"))
            ),
            popularity=self._float_value(
                payload.get("ratingKinopoiskVoteCount", payload.get("ratingVoteCount"))
            ),
            genre_ids=[self._kinopoisk_genre_id(name) for name in genre_names],
        )

    def _kinopoisk_season_summary(
        self,
        media_id: int,
        payload: dict[str, Any],
    ) -> SeasonSummary:
        number = self._int_value(payload.get("number")) or 0
        raw_episodes = payload.get("episodes")
        episodes = raw_episodes if isinstance(raw_episodes, list) else []
        air_dates = [
            date
            for item in episodes
            if isinstance(item, dict)
            and (date := self._optional_text(item.get("releaseDate"))) is not None
        ]
        return SeasonSummary(
            id=self._stable_id(f"kinopoisk:{media_id}:{number}"),
            number=number,
            name=f"Сезон {number}",
            episode_count=len(episodes),
            air_date=min(air_dates) if air_dates else None,
            poster_url=None,
        )

    @classmethod
    def _kinopoisk_matches_query(cls, payload: dict[str, Any], query: str) -> bool:
        normalized_query = cls._normalize_title(query)
        if not normalized_query:
            return False
        return any(
            normalized_query == normalized_title
            or (
                len(normalized_query) >= 4
                and (
                    normalized_query in normalized_title
                    or normalized_title in normalized_query
                )
            )
            for title in cls._kinopoisk_titles(payload)
            if (normalized_title := cls._normalize_title(title))
        )

    @staticmethod
    def _kinopoisk_matches_kind(payload: dict[str, Any], kind: MediaKind) -> bool:
        media_type = str(payload.get("type") or "").upper()
        series_types = {"TV_SERIES", "MINI_SERIES", "TV_SHOW"}
        return (media_type in series_types) == (kind == "series")

    @staticmethod
    def _kinopoisk_titles(payload: dict[str, Any]) -> tuple[str, ...]:
        result: list[str] = []
        for field in ("nameRu", "nameEn", "nameOriginal"):
            value = payload.get(field)
            if isinstance(value, str) and value.strip() and value.strip() not in result:
                result.append(value.strip())
        return tuple(result)

    @staticmethod
    def _kinopoisk_genre_names(payload: dict[str, Any]) -> list[str]:
        raw_genres = payload.get("genres")
        if not isinstance(raw_genres, list):
            return []
        return [
            name
            for item in raw_genres
            if isinstance(item, dict)
            and (name := item.get("genre"))
            and isinstance(name, str)
        ]

    @classmethod
    def _media_matches_title(cls, media: MediaCard, title: str) -> bool:
        expected = cls._normalize_title(title)
        return expected in {
            cls._normalize_title(media.title),
            cls._normalize_title(media.original_title),
        }

    @classmethod
    def _same_catalogue_title(cls, first: MediaCard, second: MediaCard) -> bool:
        first_titles = {
            cls._normalize_title(first.title),
            cls._normalize_title(first.original_title),
        }
        second_titles = {
            cls._normalize_title(second.title),
            cls._normalize_title(second.original_title),
        }
        same_year = first.year is None or second.year is None or first.year == second.year
        return same_year and bool((first_titles - {""}) & (second_titles - {""}))

    @staticmethod
    def _normalize_title(value: str) -> str:
        return re.sub(r"[^0-9a-zа-я]+", " ", value.casefold().replace("ё", "е")).strip()

    @staticmethod
    def _encode_kinopoisk_id(kinopoisk_id: int) -> int | None:
        public_id = KINOPOISK_ID_OFFSET + kinopoisk_id
        return public_id if 0 < kinopoisk_id and public_id <= MAX_PUBLIC_MEDIA_ID else None

    @staticmethod
    def _is_kinopoisk_id(media_id: int) -> bool:
        return KINOPOISK_ID_OFFSET < media_id <= MAX_PUBLIC_MEDIA_ID

    @staticmethod
    def _kinopoisk_genre_id(name: str) -> int:
        return -(zlib.crc32(name.casefold().encode()) & 0x7FFFFFFF or 1)

    @staticmethod
    def _stable_id(material: str) -> int:
        return zlib.crc32(material.encode()) & 0x7FFFFFFF or 1

    @staticmethod
    def _int_year(value: object) -> int | None:
        text = str(value or "")[:4]
        return int(text) if text.isdigit() else None

    @staticmethod
    def _int_value(value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _float_value(value: object) -> float:
        try:
            return float(value) if value is not None else 0
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _external_rating(cls, value: object) -> float | None:
        rating = cls._float_value(value)
        return rating if not isinstance(value, bool) and 0 < rating <= 10 else None

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
