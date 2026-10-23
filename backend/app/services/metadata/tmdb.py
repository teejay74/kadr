from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.services.metadata.exceptions import (
    MetadataNotConfiguredError,
    MetadataNotFoundError,
    MetadataUnavailableError,
)


class TMDBClient:
    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http_client = http_client
        self._settings = settings

    async def get(self, path: str, params: dict[str, str | int | bool]) -> dict[str, Any]:
        token = self._settings.tmdb_access_token
        if token is None or not token.get_secret_value().strip():
            raise MetadataNotConfiguredError("TMDB access token is not configured")

        request_params = {"language": self._settings.tmdb_language, **params}
        try:
            response = await self._http_client.get(
                path,
                params=request_params,
                headers={"Authorization": f"Bearer {token.get_secret_value()}"},
            )
        except httpx.RequestError as exc:
            raise MetadataUnavailableError("TMDB request failed") from exc

        if response.status_code == 404:
            raise MetadataNotFoundError("Media was not found")
        if response.status_code in {401, 403}:
            raise MetadataNotConfiguredError("TMDB rejected the configured access token")
        if response.status_code == 429 or response.status_code >= 500:
            raise MetadataUnavailableError("TMDB is temporarily unavailable")
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise MetadataUnavailableError("TMDB returned an invalid response") from exc
        if not isinstance(payload, dict):
            raise MetadataUnavailableError("TMDB returned an unexpected response")
        return payload
