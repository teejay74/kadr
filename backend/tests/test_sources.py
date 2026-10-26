from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.api.dependencies import get_source_search_service
from app.core.config import Settings
from app.main import app
from app.schemas.media import MediaDetails, MediaKind
from app.services.sources.exceptions import IndexerNotConfiguredError
from app.services.sources.prowlarr import ProwlarrClient
from app.services.sources.release_parser import parse_release_seasons, parse_release_title
from app.services.sources.search import SourceSearchService


class FakeCatalog:
    async def details(self, kind: MediaKind, media_id: int) -> MediaDetails:
        return MediaDetails(
            id=media_id,
            kind=kind,
            title="Дюна: Часть вторая",
            original_title="Dune: Part Two",
            overview="",
            release_date="2024-02-27",
            year=2024,
            rating=8.0,
            popularity=100,
        )


class FakeIndexerProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def search(self, query: str, media_kind: str) -> list[dict[str, Any]]:
        self.calls.append((query, media_kind))
        return [
            {
                "guid": "release-1",
                "title": "Dune.Part.Two.2024.1080p.WEB-DL.x264.DDP5.1.RUS",
                "indexer": "Example Torrent",
                "size": 10_000,
                "seeders": 20,
                "leechers": 3,
                "protocol": "torrent",
                "downloadUrl": "http://prowlarr/secret-download-url",
            },
            {
                "guid": "release-2",
                "title": "Dune.Part.Two.2024.2160p.BluRay.REMUX.HEVC.HDR10.TrueHD.Atmos",
                "indexer": "Example Torrent",
                "size": 50_000,
                "seeders": 8,
                "leechers": 1,
                "protocol": "torrent",
            },
            {
                "title": "Usenet result",
                "indexer": "Example Usenet",
                "size": 1,
                "protocol": "usenet",
            },
        ]

    async def list_indexers(self) -> list[dict[str, Any]]:
        return [
            {
                "id": 7,
                "name": "Example Torrent",
                "enable": True,
                "protocol": "torrent",
                "privacy": "public",
            }
        ]


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        (
            "Movie.2025.1080p.WEB-DL.H264",
            {"resolution": "1080p", "source": "WEB-DL", "codec": "H264", "hdr": False},
        ),
        (
            "Movie.2025.2160p.BluRay.x265.HDR10+.DTS-HD.MA",
            {
                "resolution": "2160p",
                "source": "BluRay",
                "codec": "HEVC",
                "hdr": True,
                "hdr_format": "HDR10+",
            },
        ),
        (
            "Movie.Unknown.Release",
            {"resolution": None, "source": None, "codec": None, "hdr": False},
        ),
    ],
)
def test_release_parser_is_conservative(title: str, expected: dict[str, object]) -> None:
    parsed = parse_release_title(title)

    for field, value in expected.items():
        assert getattr(parsed, field) == value


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Breaking Bad [S01-05] BDRip", [1, 2, 3, 4, 5]),
        ("Breaking.Bad.S01-S05.Complete", [1, 2, 3, 4, 5]),
        ("Show.S01E01-S05E16.1080p", [1, 2, 3, 4, 5]),
        ("Dark Matter - S1-2E1-18 - 2024-2026 WEBRip", [1, 2]),
        ("Show.S01-S02E01-18.1080p", [1, 2]),
        ("Dark Matter - S1E1-9 - 2024 MVO WEBDL", [1]),
        ("Show.S01E01-E09.1080p", [1]),
        ("Show Seasons 2-4 WEB-DL", [2, 3, 4]),
        ("Show 2-4 сезоны WEB-DL", [2, 3, 4]),
        ("Show [S01, S03, S05]", [1, 3, 5]),
        ("Show Season 2", [2]),
        ("Movie.2025.1080p", []),
    ],
)
def test_release_season_parser_detects_single_lists_and_ranges(
    title: str,
    expected: list[int],
) -> None:
    assert parse_release_seasons(title) == expected


async def test_source_service_normalizes_filters_and_sorts() -> None:
    provider = FakeIndexerProvider()
    service = SourceSearchService(FakeCatalog(), provider)

    result = await service.search(42, "movie", "resolution", "desc")

    assert provider.calls == [("Дюна: Часть вторая 2024", "movie")]
    assert result.total == 2
    assert [item.resolution for item in result.items] == ["2160p", "1080p"]
    assert result.items[0].release_type == "REMUX"
    assert result.items[0].hdr_format == "HDR10"
    assert result.items[1].language == "RU"
    assert result.items[0].season_numbers == []
    assert "download" not in result.items[0].model_dump_json().lower()


async def test_prowlarr_client_sends_key_and_search_parameters() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Api-Key"] == "secret-key"
        assert request.url.path == "/api/v1/search"
        assert request.url.params["query"] == "Dune 2024"
        assert request.url.params["type"] == "movie"
        assert request.url.params.get_list("categories") == ["2000", "8000"]
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://prowlarr:9696",
    ) as http_client:
        client = ProwlarrClient(http_client, Settings(prowlarr_api_key="secret-key"))
        assert await client.search("Dune 2024", "movie") == []


async def test_prowlarr_client_requires_server_side_key() -> None:
    async with httpx.AsyncClient(base_url="http://prowlarr:9696") as http_client:
        client = ProwlarrClient(http_client, Settings())
        with pytest.raises(IndexerNotConfiguredError):
            await client.search("Dune 2024", "movie")


async def test_sources_endpoint_returns_normalized_results(client: AsyncClient) -> None:
    service = SourceSearchService(FakeCatalog(), FakeIndexerProvider())
    app.dependency_overrides[get_source_search_service] = lambda: service

    response = await client.get(
        "/api/v1/media/42/sources",
        params={"kind": "movie", "sort": "seeders", "order": "desc"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["media_id"] == 42
    assert payload["items"][0]["seeders"] == 20
    assert "download_url" not in payload["items"][0]


async def test_source_service_prefers_localized_title_and_falls_back() -> None:
    class EmptyThenFoundProvider(FakeIndexerProvider):
        async def search(self, query: str, media_kind: str) -> list[dict[str, Any]]:
            self.calls.append((query, media_kind))
            if query.startswith("Дюна"):
                return []
            return await super().search(query, media_kind)

    provider = EmptyThenFoundProvider()
    service = SourceSearchService(FakeCatalog(), provider)

    result = await service.search(42, "movie", "seeders", "desc")

    assert provider.calls[:2] == [
        ("Дюна: Часть вторая 2024", "movie"),
        ("Dune: Part Two 2024", "movie"),
    ]
    assert result.query == "Dune: Part Two 2024"


async def test_source_service_searches_and_resolves_a_specific_series_season() -> None:
    provider = FakeIndexerProvider()
    service = SourceSearchService(FakeCatalog(), provider)

    result = await service.search(42, "series", "seeders", "desc", season_number=2)
    resolved = await service.resolve(42, "series", result.items[0].id, season_number=2)

    assert provider.calls == [
        ("Дюна: Часть вторая 2024 S02", "series"),
        ("Дюна: Часть вторая 2024 S02", "series"),
    ]
    assert result.query == "Дюна: Часть вторая 2024 S02"
    assert all(item.season_number == 2 for item in result.items)
    assert resolved is not None
    assert resolved.release.season_number == 2


async def test_sources_endpoint_accepts_a_season_number(client: AsyncClient) -> None:
    provider = FakeIndexerProvider()
    service = SourceSearchService(FakeCatalog(), provider)
    app.dependency_overrides[get_source_search_service] = lambda: service

    response = await client.get(
        "/api/v1/media/42/sources",
        params={"kind": "series", "season_number": 2},
    )

    assert response.status_code == 200
    assert provider.calls == [("Дюна: Часть вторая 2024 S02", "series")]
    assert response.json()["items"][0]["season_number"] == 2
