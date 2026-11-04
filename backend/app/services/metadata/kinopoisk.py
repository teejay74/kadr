from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.media import MediaKind

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SearchAlias:
    titles: tuple[str, ...]
    year: int | None


class KinopoiskAliasClient:
    """Optional Russian-title lookup used to improve canonical TMDB search."""

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http_client = http_client
        self._settings = settings

    async def aliases(self, query: str, kind: MediaKind) -> list[SearchAlias]:
        api_key = self._settings.kinopoisk_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            return []

        try:
            response = await self._http_client.get(
                "/api/v2.1/films/search-by-keyword",
                params={"keyword": query, "page": 1},
                headers={"X-API-KEY": api_key.get_secret_value()},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            logger.warning("Kinopoisk alias lookup failed", exc_info=True)
            return []

        films = payload.get("films") if isinstance(payload, dict) else None
        if not isinstance(films, list):
            return []

        aliases: list[SearchAlias] = []
        for item in films:
            if not isinstance(item, dict) or not self._matches_kind(item, kind):
                continue
            titles = self._titles(item)
            if not titles:
                continue
            aliases.append(SearchAlias(titles=titles, year=self._year(item.get("year"))))
            if len(aliases) >= self._settings.kinopoisk_search_alias_limit:
                break
        return aliases

    @staticmethod
    def _matches_kind(item: dict[str, Any], kind: MediaKind) -> bool:
        media_type = str(item.get("type") or "").upper()
        series_types = {"TV_SERIES", "MINI_SERIES", "TV_SHOW"}
        return (media_type in series_types) == (kind == "series")

    @staticmethod
    def _titles(item: dict[str, Any]) -> tuple[str, ...]:
        result: list[str] = []
        for field in ("nameRu", "nameEn", "nameOriginal"):
            value = item.get(field)
            if isinstance(value, str) and value.strip() and value.strip() not in result:
                result.append(value.strip())
        return tuple(result)

    @staticmethod
    def _year(value: object) -> int | None:
        text = str(value or "")[:4]
        return int(text) if text.isdigit() else None
