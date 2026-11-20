"""Bounded TMDB image loading; DNS overrides apply only to this client."""

from __future__ import annotations

import asyncio
import logging
import re

import httpx

from app.core.config import Settings
from app.repositories.poster_cache import PosterCacheRepository
from app.services.metadata.exceptions import MetadataUnavailableError
from app.services.network.tmdb import TMDBResolver

logger = logging.getLogger(__name__)
SIZES = frozenset({"w92", "w154", "w185", "w300", "w342", "w500", "w780", "w1280", "original"})
FILENAME = re.compile(r"[A-Za-z0-9_-]{1,128}\.(?:jpg|jpeg|png|webp)")


def poster_path(size: str, filename: str) -> str | None:
    if size not in SIZES or not FILENAME.fullmatch(filename):
        return None
    return f"/api/v1/posters/{size}/{filename}"


def image_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


class PosterManager:
    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self.cache = PosterCacheRepository(settings)
        self.slots = asyncio.Semaphore(settings.poster_concurrency)
        self.locks = [asyncio.Lock() for _ in range(32)]
        self.resolver = TMDBResolver(client, settings, "image.tmdb.org")

    async def _addresses(self) -> list[str]:
        return await self.resolver.resolve()

    async def get(self, size: str, filename: str) -> tuple[bytes, str]:
        key = poster_path(size, filename)
        if key is None:
            raise ValueError("Invalid poster path")
        async with self.locks[hash(key) % len(self.locks)]:
            data = await self.cache.get(key)
            if data is not None and (mime := image_type(data)):
                return data, mime
            try:
                async with self.slots, asyncio.timeout(self.settings.poster_timeout_seconds):
                    data, mime = await self._download(size, filename)
                await self.cache.set(key, data)
                return data, mime
            except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError) as exc:
                logger.warning(
                    "Poster fetch failed: size=%s file=%s error=%s reason=%s",
                    size,
                    filename,
                    type(exc).__name__,
                    str(exc) if isinstance(exc, ValueError) else type(exc).__name__,
                )
                raise MetadataUnavailableError("Poster temporarily unavailable") from exc

    async def _download(self, size: str, filename: str) -> tuple[bytes, str]:
        addresses = await self._addresses()
        for index, address in enumerate(addresses):
            try:
                async with self.client.stream(
                    "GET",
                    f"https://{address}/t/p/{size}/{filename}",
                    headers={
                        "Host": "image.tmdb.org",
                        "Accept": "image/jpeg,image/png,image/webp",
                        "Accept-Encoding": "identity",
                    },
                    extensions={"sni_hostname": "image.tmdb.org"},
                ) as response:
                    response.raise_for_status()
                    if response.headers.get("content-encoding", "identity") != "identity":
                        raise ValueError("Encoded image response")
                    mime = response.headers.get("content-type", "").split(";")[0].lower()
                    if mime not in {"image/jpeg", "image/png", "image/webp"}:
                        raise ValueError("Unsupported image type")
                    limit = self.settings.poster_max_response_bytes
                    if int(response.headers.get("content-length", 0)) > limit:
                        raise ValueError("Oversized image")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > limit:
                            raise ValueError("Oversized image")
                    data = bytes(body)
                    if image_type(data) != mime:
                        raise ValueError("Invalid image signature")
                    return data, mime
            except httpx.TransportError:
                if index == len(addresses) - 1:
                    self.resolver.dns_expires = 0
                    raise
        raise ValueError("No CDN addresses")
