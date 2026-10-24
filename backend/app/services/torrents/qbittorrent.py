from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.services.torrents.exceptions import (
    TorrentNotConfiguredError,
    TorrentUnavailableError,
)


class QBittorrentClient:
    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http_client = http_client
        self._settings = settings

    async def version(self) -> str:
        response = await self._request("GET", "/api/v2/app/version")
        return response.text.strip()

    async def add(self, uri: str, tag: str) -> None:
        response = await self._request(
            "POST",
            "/api/v2/torrents/add",
            data={
                "urls": uri,
                "savepath": self._settings.torrent_save_path,
                "tags": tag,
                "stopCondition": "MetadataReceived",
                "autoTMM": "false",
            },
        )
        if response.text.strip().lower().startswith("fails"):
            raise TorrentUnavailableError("qBittorrent rejected the torrent")

    async def list(
        self,
        *,
        torrent_hash: str | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if torrent_hash:
            params["hashes"] = torrent_hash
        if tag:
            params["tag"] = tag
        response = await self._request("GET", "/api/v2/torrents/info", params=params)
        payload = self._json(response)
        if not isinstance(payload, list):
            raise TorrentUnavailableError("qBittorrent returned an invalid torrent list")
        return [item for item in payload if isinstance(item, dict)]

    async def files(self, torrent_hash: str) -> list[dict[str, Any]]:
        response = await self._request(
            "GET", "/api/v2/torrents/files", params={"hash": torrent_hash}
        )
        payload = self._json(response)
        if not isinstance(payload, list):
            raise TorrentUnavailableError("qBittorrent returned an invalid file list")
        return [item for item in payload if isinstance(item, dict)]

    async def set_file_priority(
        self,
        torrent_hash: str,
        file_ids: list[int],
        priority: int,
    ) -> None:
        if not file_ids:
            return
        await self._request(
            "POST",
            "/api/v2/torrents/filePrio",
            data={
                "hash": torrent_hash,
                "id": "|".join(str(file_id) for file_id in file_ids),
                "priority": str(priority),
            },
        )

    async def start(self, torrent_hash: str) -> None:
        await self._request("POST", "/api/v2/torrents/start", data={"hashes": torrent_hash})

    async def stop(self, torrent_hash: str) -> None:
        await self._request("POST", "/api/v2/torrents/stop", data={"hashes": torrent_hash})

    async def _authenticate(self) -> None:
        password = self._settings.qbittorrent_password
        if password is None or not password.get_secret_value():
            raise TorrentNotConfiguredError("qBittorrent credentials are not configured")
        try:
            response = await self._http_client.post(
                "/api/v2/auth/login",
                data={
                    "username": self._settings.qbittorrent_username,
                    "password": password.get_secret_value(),
                },
            )
        except httpx.RequestError as exc:
            raise TorrentUnavailableError("qBittorrent request failed") from exc
        accepted = response.status_code == 204 or (
            response.status_code == 200 and response.text.strip() == "Ok."
        )
        if not accepted:
            raise TorrentNotConfiguredError("qBittorrent rejected the configured credentials")

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        await self._authenticate()
        try:
            response = await self._http_client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise TorrentUnavailableError("qBittorrent request failed") from exc
        if response.status_code in {401, 403}:
            raise TorrentNotConfiguredError("qBittorrent rejected the configured credentials")
        if response.status_code == 404:
            raise TorrentUnavailableError("qBittorrent resource was not found")
        if response.status_code >= 400:
            raise TorrentUnavailableError("qBittorrent operation failed")
        return response

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            raise TorrentUnavailableError("qBittorrent returned invalid JSON") from exc
