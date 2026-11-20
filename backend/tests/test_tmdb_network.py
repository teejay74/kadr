from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.services.network.tmdb import TMDBResolver, TMDBTransport


async def test_metadata_transport_uses_doh_and_preserves_tls_host(tmp_path: Path) -> None:
    dns_calls = 0

    def dns(request: httpx.Request) -> httpx.Response:
        nonlocal dns_calls
        dns_calls += 1
        assert request.url.host == "8.8.8.8"
        assert request.url.params["name"] == "api.themoviedb.org"
        return httpx.Response(
            200,
            json={
                "Status": 0,
                "Answer": [
                    {"type": 1, "data": "1.1.1.1", "TTL": 60},
                ],
            },
        )

    def upstream(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "1.1.1.1"
        assert request.url.path == "/3/movie/299534"
        assert request.headers["Host"] == "api.themoviedb.org"
        assert request.extensions["sni_hostname"] == "api.themoviedb.org"
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(200, json={"id": 299534})

    async with httpx.AsyncClient(transport=httpx.MockTransport(dns)) as client:
        transport = TMDBTransport(TMDBResolver(client, Settings(), "api.themoviedb.org"))
        await transport.transport.aclose()
        transport.transport = httpx.MockTransport(upstream)
        async with httpx.AsyncClient(transport=transport) as metadata:
            for _ in range(2):
                response = await metadata.get(
                    "https://api.themoviedb.org/3/movie/299534",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert response.json()["id"] == 299534
        assert dns_calls == 1


async def test_metadata_rejects_poisoned_dns_without_sending_token() -> None:
    def dns(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "Status": 0,
                "Answer": [
                    {"type": 1, "data": "127.0.0.1", "TTL": 60},
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(dns)) as client:
        transport = TMDBTransport(TMDBResolver(client, Settings(), "api.themoviedb.org"))
        async with httpx.AsyncClient(transport=transport) as metadata:
            with pytest.raises(httpx.ConnectError, match="DNS lookup failed"):
                await metadata.get("https://api.themoviedb.org/3/movie/299534")
            with pytest.raises(httpx.ConnectError, match="Unsupported TMDB origin"):
                await metadata.get("https://example.com/")


async def test_doh_http_failure_is_a_controlled_metadata_error() -> None:
    from app.services.metadata.exceptions import MetadataUnavailableError
    from app.services.metadata.tmdb import TMDBClient

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(503),
        )
    ) as dns:
        settings = Settings(tmdb_access_token="test-secret")
        transport = TMDBTransport(TMDBResolver(dns, settings, "api.themoviedb.org"))
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://api.themoviedb.org/3",
        ) as client:
            with pytest.raises(MetadataUnavailableError, match="TMDB request failed"):
                await TMDBClient(client, settings).get("/movie/299534", {})
