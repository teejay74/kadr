from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_catalog_service
from app.core.config import Settings
from app.main import app
from app.models.metadata_cache import MetadataCache
from app.repositories.metadata_cache import MetadataCacheRepository
from app.services.metadata.catalog import CatalogService
from app.services.metadata.exceptions import MetadataNotConfiguredError, MetadataUnavailableError
from app.services.metadata.kinopoisk import KinopoiskClient
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


class FakeKinopoiskClient:
    def __init__(self, payloads: dict[str, dict[str, Any]]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, dict[str, str | int | bool]]] = []

    async def get(self, path: str, params: dict[str, str | int | bool]) -> dict[str, Any]:
        self.calls.append((path, params))
        return self.payloads[path]


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


def kinopoisk_game_payloads() -> dict[str, dict[str, Any]]:
    return {
        "/api/v2.1/films/search-by-keyword": {
            "films": [
                {
                    "filmId": 77,
                    "nameRu": "Игра престолов",
                    "nameEn": "Game of Thrones",
                    "year": "2011",
                    "type": "TV_SERIES",
                    "posterUrlPreview": "https://kp.example/game-small.jpg",
                    "genres": [{"genre": "фэнтези"}],
                }
            ]
        },
        "/api/v2.2/films/77": {
            "kinopoiskId": 77,
            "nameRu": "Игра престолов",
            "nameOriginal": "Game of Thrones",
            "year": 2011,
            "type": "TV_SERIES",
            "description": "Борьба за Железный трон.",
            "posterUrl": "https://kp.example/game.jpg",
            "ratingKinopoisk": 9.0,
            "genres": [{"genre": "фэнтези"}],
            "completed": True,
        },
        "/api/v2.2/films/77/seasons": {
            "items": [
                {
                    "number": 1,
                    "episodes": [
                        {
                            "episodeNumber": 1,
                            "nameRu": "Зима близко",
                            "releaseDate": "2011-04-17",
                        }
                    ],
                }
            ]
        },
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


async def test_discovery_applies_new_release_and_russian_age_filters(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    fake_client = FakeTMDBClient(movie_page_payload())
    service = CatalogService(fake_client, MetadataCacheRepository(session), Settings())
    app.dependency_overrides[get_catalog_service] = lambda: service

    response = await client.get(
        "/api/v1/movies?sort=newest&genre=16&age_rating=6%2B&released_within_days=365"
    )

    assert response.status_code == 200
    params = fake_client.calls[0][1]
    assert params["with_genres"] == 16
    assert params["certification_country"] == "RU"
    assert params["certification"] == "6+"
    assert params["release_date.gte"] < params["release_date.lte"]
    assert params["with_release_type"] == 4


async def test_search_uses_kinopoisk_alias_but_keeps_tmdb_identity(
    session: AsyncSession,
) -> None:
    empty_payload = {"page": 1, "total_pages": 0, "total_results": 0, "results": []}
    fake_client = FakeTMDBClient(empty_payload)
    fake_kinopoisk = FakeKinopoiskClient(
        {
            "/api/v2.1/films/search-by-keyword": {
                "films": [
                    {
                        "filmId": 1,
                        "nameRu": "Брат",
                        "nameEn": "Brother",
                        "year": "1997",
                        "type": "FILM",
                    }
                ]
            }
        }
    )
    service = CatalogService(
        fake_client,
        MetadataCacheRepository(session),
        Settings(),
        fake_kinopoisk,
    )

    original_get = fake_client.get

    async def get(path: str, params: dict[str, str | int | bool]) -> dict[str, Any]:
        payload = await original_get(path, params)
        if params.get("query") != "Brother":
            return payload
        return {
            "page": 1,
            "total_pages": 1,
            "total_results": 1,
            "results": [
                {
                    "id": 11,
                    "title": "Брат",
                    "original_title": "Brother",
                    "release_date": "1997-12-12",
                }
            ],
        }

    fake_client.get = get  # type: ignore[method-assign]
    result = await service.search("movie", "Брат", page=1, year=None)

    assert [item.id for item in result.items] == [11]
    assert fake_client.calls[1][1]["query"] == "Brother"
    assert fake_client.calls[1][1]["year"] == 1997


async def test_kinopoisk_client_requires_key_and_authenticates() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers["X-API-KEY"] == "kp-secret"
        return httpx.Response(
            200,
            json={
                "films": [
                    {
                        "filmId": 1,
                        "nameRu": "Брат",
                        "nameEn": "Brother",
                        "year": "1997",
                        "type": "FILM",
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://kp.example") as http_client:
        disabled = KinopoiskClient(http_client, Settings())
        with pytest.raises(MetadataNotConfiguredError):
            await disabled.get("/api/v2.1/films/search-by-keyword", {"keyword": "Брат"})
        enabled = KinopoiskClient(http_client, Settings(kinopoisk_api_key="kp-secret"))
        payload = await enabled.get(
            "/api/v2.1/films/search-by-keyword",
            {"keyword": "Брат"},
        )

    assert calls == 1
    assert payload["films"][0]["nameEn"] == "Brother"


async def test_search_returns_exact_kinopoisk_fallback_and_rejects_fuzzy_results(
    session: AsyncSession,
) -> None:
    empty_payload = {"page": 1, "total_pages": 0, "total_results": 0, "results": []}
    fake_kinopoisk = FakeKinopoiskClient(
        {
            "/api/v2.1/films/search-by-keyword": {
                "films": [
                    {
                        "filmId": 1_115_558,
                        "nameRu": "Котёнок Котэ",
                        "nameEn": "Kote TV",
                        "year": "2015",
                        "type": "TV_SERIES",
                        "description": "Музыкальные видео для малышей.",
                        "posterUrlPreview": "https://kp.example/kote-small.jpg",
                        "rating": "8.0",
                        "genres": [{"genre": "мультфильм"}],
                    },
                    {
                        "filmId": 2,
                        "nameRu": "Разрешите обратиться",
                        "year": "2023",
                        "type": "TV_SERIES",
                    },
                ]
            }
        }
    )
    service = CatalogService(
        FakeTMDBClient(empty_payload),
        MetadataCacheRepository(session),
        Settings(),
        fake_kinopoisk,
    )

    result = await service.search("series", "Котенок Котэ", page=1, year=None)

    assert [(item.id, item.title, item.year) for item in result.items] == [
        (1_501_115_558, "Котёнок Котэ", 2015)
    ]
    assert result.items[0].poster_url == "https://kp.example/kote-small.jpg"


async def test_kinopoisk_fallback_provides_details_and_season_metadata(
    session: AsyncSession,
) -> None:
    kinopoisk_id = 1_115_558
    public_id = 1_501_115_558
    fake_kinopoisk = FakeKinopoiskClient(
        {
            f"/api/v2.2/films/{kinopoisk_id}": {
                "kinopoiskId": kinopoisk_id,
                "nameRu": "Котёнок Котэ",
                "nameOriginal": "Kote TV",
                "year": 2015,
                "type": "TV_SERIES",
                "description": "Музыкальный проект и канал.",
                "posterUrl": "https://kp.example/kote.jpg",
                "coverUrl": "https://kp.example/kote-cover.jpg",
                "ratingKinopoisk": 8.0,
                "ratingKinopoiskVoteCount": 1_200,
                "genres": [{"genre": "мультфильм"}, {"genre": "детский"}],
                "countries": [{"country": "Россия"}],
                "completed": True,
            },
            f"/api/v2.2/films/{kinopoisk_id}/seasons": {
                "total": 1,
                "items": [
                    {
                        "number": 1,
                        "episodes": [
                            {
                                "seasonNumber": 1,
                                "episodeNumber": 1,
                                "nameRu": "Светофор",
                                "synopsis": "Зачем нужен светофор?",
                                "releaseDate": "2015-01-01",
                            }
                        ],
                    }
                ],
            },
        }
    )
    service = CatalogService(
        FakeTMDBClient({}),
        MetadataCacheRepository(session),
        Settings(),
        fake_kinopoisk,
    )

    details = await service.details("series", public_id)
    season = await service.season(public_id, 1)

    assert details.title == "Котёнок Котэ"
    assert details.original_title == "Kote TV"
    assert details.season_count == 1
    assert details.episode_count == 1
    assert details.status == "Завершён"
    assert [genre.name for genre in details.genres] == ["мультфильм", "детский"]
    assert season.series_id == public_id
    assert [(item.number, item.name) for item in season.episodes] == [(1, "Светофор")]
    assert [call[0] for call in fake_kinopoisk.calls].count(
        f"/api/v2.2/films/{kinopoisk_id}/seasons"
    ) == 1


async def test_details_endpoint_uses_kinopoisk_when_tmdb_is_unavailable(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    fake_tmdb = FakeTMDBClient({})
    fake_tmdb.unavailable = True
    fake_kinopoisk = FakeKinopoiskClient(kinopoisk_game_payloads())
    service = CatalogService(
        fake_tmdb,
        MetadataCacheRepository(session),
        Settings(),
        fake_kinopoisk,
    )
    app.dependency_overrides[get_catalog_service] = lambda: service

    response = await client.get(
        "/api/v1/series/1399",
        params={"fallback_title": "Игра престолов", "fallback_year": 2011},
    )

    assert response.status_code == 200
    assert response.json()["id"] == 1_500_000_077
    assert response.json()["title"] == "Игра престолов"
    assert response.json()["seasons"][0]["episode_count"] == 1

    wrong_year = await client.get(
        "/api/v1/series/1399",
        params={"fallback_title": "Игра престолов", "fallback_year": 2012},
    )
    assert wrong_year.status_code == 502
    assert wrong_year.json()["code"] == "metadata_unavailable"


async def test_search_uses_kinopoisk_when_tmdb_is_unavailable(
    session: AsyncSession,
) -> None:
    fake_tmdb = FakeTMDBClient({})
    fake_tmdb.unavailable = True
    service = CatalogService(
        fake_tmdb,
        MetadataCacheRepository(session),
        Settings(),
        FakeKinopoiskClient(kinopoisk_game_payloads()),
    )

    result = await service.search("series", "Игра престолов", page=1, year=2011)

    assert [(item.id, item.title) for item in result.items] == [
        (1_500_000_077, "Игра престолов")
    ]


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
