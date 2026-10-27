from __future__ import annotations

from typing import Any

import httpx
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_catalog_service
from app.core.config import Settings
from app.main import app
from app.models.metadata_cache import MetadataCache
from app.repositories.metadata_cache import MetadataCacheRepository
from app.services.metadata.catalog import CatalogService
from app.services.metadata.exceptions import MetadataUnavailableError
from app.services.metadata.tmdb import TMDBClient


class FakeTMDBClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, str | int | bool]]] = []
        self.unavailable = False

    async def get(self, path: str, params: dict[str, str | int | bool]) -> dict[str, Any]:
        self.calls.append((path, params))
        if self.unavailable:
            raise MetadataUnavailableError("provider unavailable")
        return self.payload


def movie_page_payload() -> dict[str, Any]:
    return {
        "page": 1,
        "total_pages": 3,
        "total_results": 42,
        "results": [
            {
                "id": 11,
                "title": "Звёздные войны",
                "original_title": "Star Wars",
                "overview": "A long time ago.",
                "release_date": "1977-05-25",
                "poster_path": "/poster.jpg",
                "backdrop_path": "/backdrop.jpg",
                "vote_average": 8.2,
                "popularity": 99.5,
                "genre_ids": [12, 878],
            }
        ],
    }


def season_payload() -> dict[str, Any]:
    return {
        "id": 501,
        "season_number": 2,
        "name": "Сезон 2",
        "overview": "Продолжение истории.",
        "air_date": "2025-01-10",
        "poster_path": "/season.jpg",
        "episodes": [
            {
                "id": 601,
                "season_number": 2,
                "episode_number": 1,
                "name": "Возвращение",
                "overview": "Первая серия сезона.",
                "air_date": "2025-01-10",
                "runtime": 52,
                "still_path": "/episode.jpg",
                "vote_average": 8.4,
            }
        ],
    }


async def test_movies_endpoint_uses_catalog_service_and_normalizes_tmdb(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    fake_client = FakeTMDBClient(movie_page_payload())
    service = CatalogService(
        fake_client,
        MetadataCacheRepository(session),
        Settings(),
    )
    app.dependency_overrides[get_catalog_service] = lambda: service

    response = await client.get("/api/v1/movies?sort=rating&genre=12&year=1977")

    assert response.status_code == 200
    assert response.json()["items"][0] == {
        "id": 11,
        "kind": "movie",
        "title": "Звёздные войны",
        "original_title": "Star Wars",
        "overview": "A long time ago.",
        "release_date": "1977-05-25",
        "year": 1977,
        "poster_url": "https://image.tmdb.org/t/p/w500/poster.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/backdrop.jpg",
        "rating": 8.2,
        "popularity": 99.5,
        "genre_ids": [12, 878],
    }
    assert fake_client.calls[0][0] == "/discover/movie"
    assert fake_client.calls[0][1]["vote_count.gte"] == 100


async def test_catalog_reuses_sqlite_cache(session: AsyncSession) -> None:
    fake_client = FakeTMDBClient(movie_page_payload())
    service = CatalogService(
        fake_client,
        MetadataCacheRepository(session),
        Settings(),
    )

    first = await service.list_media("movie", page=1, sort="popular", genre=None, year=None)
    second = await service.list_media("movie", page=1, sort="popular", genre=None, year=None)

    assert first == second
    assert len(fake_client.calls) == 1


async def test_series_season_endpoint_normalizes_and_caches_episodes(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    fake_client = FakeTMDBClient(season_payload())
    service = CatalogService(
        fake_client,
        MetadataCacheRepository(session),
        Settings(),
    )
    app.dependency_overrides[get_catalog_service] = lambda: service

    first = await client.get("/api/v1/series/42/seasons/2")
    second = await client.get("/api/v1/series/42/seasons/2")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == {
        "id": 501,
        "series_id": 42,
        "number": 2,
        "name": "Сезон 2",
        "overview": "Продолжение истории.",
        "air_date": "2025-01-10",
        "poster_url": "https://image.tmdb.org/t/p/w342/season.jpg",
        "episodes": [
            {
                "id": 601,
                "season_number": 2,
                "number": 1,
                "name": "Возвращение",
                "overview": "Первая серия сезона.",
                "air_date": "2025-01-10",
                "runtime_minutes": 52,
                "still_url": "https://image.tmdb.org/t/p/w500/episode.jpg",
                "rating": 8.4,
            }
        ],
    }
    assert fake_client.calls == [("/tv/42/season/2", {})]


async def test_catalog_uses_expired_cache_during_provider_outage(
    session: AsyncSession,
) -> None:
    fake_client = FakeTMDBClient(movie_page_payload())
    service = CatalogService(
        fake_client,
        MetadataCacheRepository(session),
        Settings(),
    )
    expected = await service.list_media(
        "movie",
        page=1,
        sort="popular",
        genre=None,
        year=None,
    )
    await session.execute(update(MetadataCache).values(expires_at=0))
    await session.commit()
    fake_client.unavailable = True

    actual = await service.list_media(
        "movie",
        page=1,
        sort="popular",
        genre=None,
        year=None,
    )

    assert actual == expected
    assert len(fake_client.calls) == 2


async def test_tmdb_client_sends_bearer_token_and_language() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret-token"
        assert request.url.params["language"] == "ru-RU"
        return httpx.Response(200, json={"page": 1, "results": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://api.example",
    ) as http_client:
        client = TMDBClient(http_client, Settings(tmdb_access_token="secret-token"))
        payload = await client.get("/discover/movie", {"page": 1})

    assert payload == {"page": 1, "results": []}
