"""Dedicated DNS-JSON resolver for the two fixed TMDB hosts."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import time

import httpx

from app.core.config import Settings
from app.services.metadata.exceptions import MetadataUnavailableError

logger = logging.getLogger(__name__)


class TMDBResolver:
    def __init__(self, client: httpx.AsyncClient, settings: Settings, hostname: str) -> None:
        if hostname not in {"image.tmdb.org", "api.themoviedb.org"}:
            raise ValueError("Unsupported TMDB host")
        self.client = client
        self.settings = settings
        self.hostname = hostname
        self.dns_lock = asyncio.Lock()
        self.addresses: list[str] = []
        self.dns_expires = 0.0

    async def resolve(self) -> list[str]:
        async with self.dns_lock:
            if self.addresses and self.dns_expires > time.monotonic():
                return self.addresses
            providers = [(self.settings.poster_doh_url, self.settings.poster_doh_bootstrap_ip)]
            if self.settings.tmdb_doh_fallback_url:
                providers.append((self.settings.tmdb_doh_fallback_url,
                                  self.settings.tmdb_doh_fallback_bootstrap_ip))
            for index, (url, bootstrap) in enumerate(providers):
                try:
                    return await self._lookup(url, bootstrap)
                except (httpx.HTTPError, ValueError, TypeError, KeyError,
                        MetadataUnavailableError) as exc:
                    logger.warning(
                        "TMDB DNS provider rejected: host=%s provider=%s reason=%s",
                        self.hostname, index,
                        str(exc) if isinstance(exc, ValueError) else type(exc).__name__,
                    )
                    if index == len(providers) - 1:
                        raise
            raise ValueError("No TMDB DNS providers")

    async def _lookup(self, resolver_url: str, bootstrap_ip: str) -> list[str]:
        url = httpx.URL(resolver_url)
        if url.scheme != "https" or not url.host or url.userinfo:
            raise MetadataUnavailableError("Invalid TMDB resolver configuration")
        headers = {
            "Accept": "application/dns-json",
            "Host": url.netloc.decode(),
            "Accept-Encoding": "identity",
        }
        extensions = {"sni_hostname": url.host}
        if bootstrap_ip:
            address = str(ipaddress.ip_address(bootstrap_ip))
            url = url.copy_with(host=address)
        async with self.client.stream(
            "GET",
            url,
            params={"name": self.hostname, "type": "A"},
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
                raise ValueError("Non-public TMDB address")
            addresses.append(str(address))
            ttls.append(int(answer.get("TTL", 60)))
        if not addresses:
            raise ValueError("No TMDB addresses")
        self.addresses = addresses[:8]
        self.dns_expires = time.monotonic() + max(1, min(300, *ttls))
        return self.addresses

class TMDBTransport(httpx.AsyncBaseTransport):
    """Connect to resolved addresses while retaining the original Host and TLS SNI."""

    def __init__(self, resolver: TMDBResolver) -> None:
        self.resolver = resolver
        self.transport = httpx.AsyncHTTPTransport(
            retries=0,
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != self.resolver.hostname or request.url.scheme != "https":
            raise httpx.ConnectError("Unsupported TMDB origin", request=request)
        try:
            async with asyncio.timeout(self.resolver.settings.tmdb_timeout_seconds):
                addresses = await self.resolver.resolve()
                for index, address in enumerate(addresses):
                    headers = request.headers.copy()
                    headers["Host"] = request.url.netloc.decode()
                    outgoing = httpx.Request(
                        request.method,
                        request.url.copy_with(host=address),
                        headers=headers,
                        stream=request.stream,
                        extensions={**request.extensions, "sni_hostname": self.resolver.hostname},
                    )
                    try:
                        return await self.transport.handle_async_request(outgoing)
                    except (httpx.ConnectError, httpx.ConnectTimeout):
                        if index == len(addresses) - 1:
                            self.resolver.dns_expires = 0
                            raise
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
            TimeoutError,
            MetadataUnavailableError,
        ) as exc:
            logger.warning(
                "TMDB transport failed: host=%s error=%s reason=%s",
                self.resolver.hostname,
                type(exc).__name__,
                str(exc) if isinstance(exc, ValueError) else type(exc).__name__,
            )
            raise httpx.ConnectError("TMDB DNS lookup failed", request=request) from exc
        raise httpx.ConnectError("TMDB DNS returned no addresses", request=request)

    async def aclose(self) -> None:
        await self.transport.aclose()
