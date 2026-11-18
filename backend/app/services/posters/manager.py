"""Bounded TMDB image loading; DNS overrides apply only to this client."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
import time

import httpx

from app.core.config import Settings
from app.repositories.poster_cache import PosterCacheRepository
from app.services.metadata.exceptions import MetadataUnavailableError

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
        self.dns_lock = asyncio.Lock()
        self.addresses: list[str] = []
        self.dns_expires = 0.0

    async def _addresses(self) -> list[str]:
        async with self.dns_lock:
            if self.addresses and self.dns_expires > time.monotonic():
                return self.addresses
            url = httpx.URL(self.settings.poster_doh_url)
            if url.scheme != "https" or not url.host or url.userinfo:
                raise MetadataUnavailableError("Invalid poster resolver configuration")
            headers = {
                "Accept": "application/dns-json",
                "Host": url.netloc.decode(),
                "Accept-Encoding": "identity",
            }
            extensions = {"sni_hostname": url.host}
            if self.settings.poster_doh_bootstrap_ip:
                address = str(ipaddress.ip_address(self.settings.poster_doh_bootstrap_ip))
                url = url.copy_with(host=address)
            async with self.client.stream(
                "GET",
                url,
                params={"name": "image.tmdb.org", "type": "A"},
                headers=headers,
                extensions=extensions,
            ) as response:
                response.raise_for_status()
                if response.headers.get("content-encoding", "identity") != "identity":
                    raise ValueError("Encoded DNS response")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 65536:
                        raise ValueError("Oversized DNS response")
            payload = json.loads(body)
            if not isinstance(payload, dict) or payload.get("Status") != 0:
                raise ValueError("DNS lookup failed")
            addresses: list[str] = []
            ttls: list[int] = []
            for answer in payload.get("Answer", []):
                if not isinstance(answer, dict):
                    raise ValueError("Invalid DNS answer")
                if answer.get("type") != 1:
                    continue
                address = ipaddress.ip_address(answer["data"])
                if not address.is_global or address.version != 4:
                    raise ValueError("Non-public CDN address")
                addresses.append(str(address))
                ttls.append(int(answer.get("TTL", 60)))
            if not addresses:
                raise ValueError("No CDN addresses")
            self.addresses = addresses[:8]
            self.dns_expires = time.monotonic() + max(1, min(300, *ttls))
            return self.addresses

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
                    "Poster fetch failed: size=%s file=%s error=%s",
                    size,
                    filename,
                    type(exc).__name__,
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
                    self.dns_expires = 0
                    raise
        raise ValueError("No CDN addresses")
