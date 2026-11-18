from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.main import app
from app.services.metadata.exceptions import MetadataUnavailableError
from app.services.posters.manager import PosterManager, poster_path

JPEG = b"\xff\xd8\xff\xe0" + b"image-content"


def settings(tmp_path: Path, **kwargs: object) -> Settings:
    return Settings(poster_cache_root=str(tmp_path / "posters"), **kwargs)


@pytest.mark.parametrize(
    "size,name",
    [
        ("w501", "poster.jpg"),
        ("w500", "../poster.jpg"),
        ("w500", "https://evil.jpg"),
        ("w500", "a.svg"),
        ("w500", "a.jpg?url=evil"),
        ("w500", "a%2f.jpg"),
    ],
)
def test_invalid_paths(size: str, name: str) -> None:
    assert poster_path(size, name) is None


async def test_doh_tls_host_cache_and_persistence(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/resolve":
            assert request.url.host == "8.8.8.8"
            assert request.headers["host"] == "dns.google"
            assert request.extensions["sni_hostname"] == "dns.google"
            assert request.url.params["name"] == "image.tmdb.org"
            return httpx.Response(
                200,
                json={
                    "Status": 0,
                    "Answer": [
                        {"type": 1, "data": "1.1.1.1", "TTL": 60},
                    ],
                },
            )
        assert request.url.host == "1.1.1.1"
        assert request.url.path == "/t/p/w500/poster.jpg"
        assert request.headers["host"] == "image.tmdb.org"
        assert request.extensions["sni_hostname"] == "image.tmdb.org"
        return httpx.Response(200, content=JPEG, headers={"Content-Type": "image/jpeg"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        manager = PosterManager(client, settings(tmp_path))
        assert await manager.get("w500", "poster.jpg") == (JPEG, "image/jpeg")
        assert await manager.get("w500", "poster.jpg") == (JPEG, "image/jpeg")
        second = PosterManager(client, settings(tmp_path))
        assert await second.get("w500", "poster.jpg") == (JPEG, "image/jpeg")
        assert len(calls) == 2


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(302, headers={"Location": "http://127.0.0.1/"}),
        httpx.Response(500),
        httpx.Response(404),
        httpx.Response(200, content=b"<html>", headers={"Content-Type": "text/html"}),
        httpx.Response(200, content=b"not an image", headers={"Content-Type": "image/jpeg"}),
        httpx.Response(
            200, content=JPEG, headers={"Content-Type": "image/jpeg", "Content-Length": "99999999"}
        ),
        httpx.Response(200, content=JPEG * 100, headers={"Content-Type": "image/jpeg"}),
    ],
)
async def test_rejects_invalid_or_oversized_and_never_caches(
    tmp_path: Path,
    response: httpx.Response,
) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response)) as client:
        manager = PosterManager(client, settings(tmp_path, poster_max_response_bytes=1024))
        manager.addresses = ["1.1.1.1"]
        manager.dns_expires = float("inf")
        with pytest.raises(MetadataUnavailableError):
            await manager.get("w500", "poster.jpg")
        assert not list(tmp_path.rglob("*.img"))


@pytest.mark.parametrize("address", ["127.0.0.1", "192.168.1.1", "0.0.0.0", "169.254.1.1"])
async def test_rejects_private_dns_addresses(tmp_path: Path, address: str) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "Status": 0,
                "Answer": [
                    {"type": 1, "data": address, "TTL": 60},
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(MetadataUnavailableError):
            await PosterManager(client, settings(tmp_path)).get("w500", "poster.jpg")


async def test_timeout(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(MetadataUnavailableError):
            await PosterManager(client, settings(tmp_path)).get("w500", "poster.jpg")


async def test_cache_bound_and_expiry(tmp_path: Path) -> None:
    import os

    manager = PosterManager(httpx.AsyncClient(), settings(tmp_path, poster_cache_max_bytes=1024))
    try:
        await manager.cache.set("first", JPEG * 40)
        await manager.cache.set("second", JPEG * 40)
        assert sum(p.stat().st_size for p in tmp_path.rglob("*.img")) <= 1024
        assert await manager.cache.get("first") is None
        path = manager.cache._path("second")
        os.utime(path, (0, 0))
        assert await manager.cache.get("second") is None
    finally:
        await manager.client.aclose()


async def test_endpoint(client: httpx.AsyncClient, tmp_path: Path) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(500))
    ) as upstream:
        manager = PosterManager(upstream, settings(tmp_path))
        app.state.poster_manager = manager
        await manager.cache.set("/api/v1/posters/w500/a.jpg", JPEG)
        response = await client.get("/api/v1/posters/w500/a.jpg")
        assert response.status_code == 200
        assert response.content == JPEG
        assert response.headers["content-type"] == "image/jpeg"
        assert "max-age=" in response.headers["cache-control"]
        assert (await client.get("/api/v1/posters/w501/a.jpg")).status_code == 422
        assert (await client.get("/api/v1/posters/w500/a.jpg?url=http://evil")).status_code == 422
        failed = await client.get("/api/v1/posters/w500/missing.jpg")
        assert failed.status_code == 502
        assert failed.json()["code"] == "metadata_unavailable"


@pytest.mark.parametrize("payload", [
    [], {"Status": 3}, {"Status": 0, "Answer": []},
    {"Status": 0, "Answer": ["bad"]}, {"Status": 0, "Answer": None},
])
async def test_invalid_dns_responses(tmp_path: Path, payload: object) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=payload),
    )) as client:
        with pytest.raises(MetadataUnavailableError):
            await PosterManager(client, settings(tmp_path)).get("w500", "poster.jpg")


async def test_cache_does_not_follow_symlinks_or_remove_unrelated_files(tmp_path: Path) -> None:
    async with httpx.AsyncClient() as client:
        manager = PosterManager(client, settings(tmp_path, poster_cache_max_bytes=1024))
        manager.cache.root.mkdir()
        media = tmp_path / "saved.jpg"
        media.write_bytes(JPEG)
        manager.cache._path("symlink").symlink_to(media)
        unrelated = manager.cache.root / "saved.img"
        unrelated.write_bytes(JPEG)
        assert await manager.cache.get("symlink") is None
        await manager.cache.set("one", JPEG * 40)
        await manager.cache.set("two", JPEG * 40)
        assert unrelated.read_bytes() == JPEG
        assert media.read_bytes() == JPEG
