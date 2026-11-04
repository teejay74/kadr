from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.services.metadata.exceptions import (
    MetadataNotConfiguredError,
    MetadataNotFoundError,
    MetadataUnavailableError,
)


class KinopoiskClient:
    """Authenticated Kinopoisk Unofficial metadata transport."""

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http_client = http_client
        self._settings = settings

    async def get(
        self,
        path: str,
        params: dict[str, str | int | bool],
    ) -> dict[str, Any]:
        api_key = self._settings.kinopoisk_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise MetadataNotConfiguredError("Kinopoisk API key is not configured")

        try:
            response = await self._http_client.get(
                path,
                params=params,
                headers={"X-API-KEY": api_key.get_secret_value()},
            )
        except httpx.RequestError as exc:
            raise MetadataUnavailableError("Kinopoisk request failed") from exc

        if response.status_code == 404:
            raise MetadataNotFoundError("Media was not found")
        if response.status_code in {401, 403}:
            raise MetadataNotConfiguredError("Kinopoisk rejected the configured API key")
        if response.status_code == 429 or response.status_code >= 500:
            raise MetadataUnavailableError("Kinopoisk is temporarily unavailable")
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise MetadataUnavailableError("Kinopoisk returned an invalid response") from exc
        if not isinstance(payload, dict):
            raise MetadataUnavailableError("Kinopoisk returned an unexpected response")
        return payload
