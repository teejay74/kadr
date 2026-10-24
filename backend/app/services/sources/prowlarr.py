from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.services.sources.exceptions import (
    IndexerNotConfiguredError,
    IndexerUnavailableError,
)


class ProwlarrClient:
    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http_client = http_client
        self._settings = settings

    def _headers(self) -> dict[str, str]:
        api_key = self._settings.prowlarr_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise IndexerNotConfiguredError("Prowlarr API key is not configured")
        return {"X-Api-Key": api_key.get_secret_value()}

    async def search(self, query: str, media_kind: str) -> list[dict[str, Any]]:
        media_category = 2000 if media_kind == "movie" else 5000
        params: list[tuple[str, str | int]] = [
            ("query", query),
            ("type", "movie" if media_kind == "movie" else "tvsearch"),
            ("categories", media_category),
            # Some indexers, including RuTor, expose search results as Other.
            ("categories", 8000),
            ("limit", self._settings.prowlarr_search_limit),
            ("offset", 0),
        ]
        payload = await self._get("/api/v1/search", params=params)
        if not isinstance(payload, list):
            raise IndexerUnavailableError("Prowlarr returned an unexpected search response")
        return [item for item in payload if isinstance(item, dict)]

    async def list_indexers(self) -> list[dict[str, Any]]:
        payload = await self._get("/api/v1/indexer")
        if not isinstance(payload, list):
            raise IndexerUnavailableError("Prowlarr returned an unexpected indexer response")
        return [item for item in payload if isinstance(item, dict)]

    async def _get(
        self,
        path: str,
        *,
        params: list[tuple[str, str | int]] | None = None,
    ) -> Any:
        try:
            response = await self._http_client.get(
                path,
                params=params,
                headers=self._headers(),
            )
        except httpx.RequestError as exc:
            raise IndexerUnavailableError("Prowlarr request failed") from exc
        if response.status_code in {401, 403}:
            raise IndexerNotConfiguredError("Prowlarr rejected the configured API key")
        if response.status_code == 429 or response.status_code >= 500:
            raise IndexerUnavailableError("Prowlarr is temporarily unavailable")
        try:
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise IndexerUnavailableError("Prowlarr returned an invalid response") from exc
