from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.api.dependencies import get_torrent_manager
from app.core.config import Settings
from app.main import app
from app.models.torrent_task import TorrentTask
from app.services.sources.search import ResolvedSource
from app.services.torrents.exceptions import TorrentFileError, TorrentStorageError
from app.services.torrents.manager import TorrentManager
from app.services.torrents.qbittorrent import QBittorrentClient


class FakeSources:
    async def resolve(self, media_id: int, media_kind: str, source_id: str) -> ResolvedSource:
        from app.schemas.sources import SourceRelease

        return ResolvedSource(
            release=SourceRelease(
                id=source_id,
                title="Sintel.2010.1080p.WEB-DL.H264",
                indexer="Test",
                size_bytes=1000,
            ),
            uri="magnet:?xt=urn:btih:abc123",
            info_hash="abc123",
        )


class FakeRepository:
    def __init__(self) -> None:
        self.tasks: dict[str, TorrentTask] = {}

    async def create(self, task: TorrentTask) -> TorrentTask:
        self.tasks[task.id] = task
        return task

    async def get(self, task_id: str) -> TorrentTask | None:
        return self.tasks.get(task_id)

    async def get_by_hash(self, torrent_hash: str) -> TorrentTask | None:
        return next(
            (task for task in self.tasks.values() if task.torrent_hash == torrent_hash),
            None,
        )

    async def get_latest_by_media(
        self,
        media_id: int,
        media_kind: str,
    ) -> TorrentTask | None:
        matches = [
            task
            for task in self.tasks.values()
            if task.media_id == media_id and task.media_kind == media_kind
        ]
        return matches[-1] if matches else None

    async def select_file(self, task: TorrentTask, file_id: int, file_path: str) -> None:
        task.selected_file_id = file_id
        task.selected_file_path = file_path

    async def set_state(self, task: TorrentTask, state: str) -> None:
        task.state = state


class FakeTorrentClient:
    def __init__(self) -> None:
        self.started = False
        self.priority_calls: list[tuple[list[int], int]] = []

    async def add(self, uri: str, tag: str) -> None:
        assert uri.startswith("magnet:")
        assert tag.startswith("kadr-")

    async def list(
        self, *, torrent_hash: str | None = None, tag: str | None = None
    ) -> list[dict[str, Any]]:
        if torrent_hash is None and tag is None:
            return []
        return [
            {
                "hash": "abc123",
                "name": "Sintel",
                "state": "downloading" if self.started else "stoppedDL",
                "progress": 0.25 if self.started else 0,
                "downloaded": 250,
                "size": 1000,
                "dlspeed": 100,
                "upspeed": 0,
                "num_leechs": 2,
                "num_seeds": 4,
                "eta": 10,
            }
        ]

    async def files(self, torrent_hash: str) -> list[dict[str, Any]]:
        return [
            {"name": "poster.jpg", "size": 10, "progress": 0, "priority": 1},
            {"name": "Sintel.mp4", "size": 990, "progress": 0, "priority": 1},
        ]

    async def set_file_priority(
        self,
        torrent_hash: str,
        file_ids: list[int],
        priority: int,
    ) -> None:
        self.priority_calls.append((file_ids, priority))

    async def start(self, torrent_hash: str) -> None:
        self.started = True

    async def stop(self, torrent_hash: str) -> None:
        self.started = False


async def test_torrent_manager_adds_selects_and_starts_real_state() -> None:
    client = FakeTorrentClient()
    repository = FakeRepository()
    manager = TorrentManager(
        client,
        FakeSources(),
        repository,
        Settings(
            qbittorrent_password="x",
            min_free_space_gb=0,
            torrent_storage_root="/tmp",
            torrent_save_path="/tmp/cache",
        ),
    )

    added = await manager.add(42, "movie", "a" * 24)
    files = await manager.files(added.id)
    selected = await manager.select_file(added.id, 1)
    started = await manager.start(added.id)

    assert added.state == "stoppedDL"
    assert [item.is_video for item in files] == [False, True]
    assert selected.selected_file_path == "Sintel.mp4"
    assert client.priority_calls == [([0, 1], 0), ([0, 1], 0), ([1], 1)]
    assert started.state == "downloading"
    assert started.progress == 0.25


async def test_torrent_manager_rejects_non_video_selection() -> None:
    manager = TorrentManager(
        FakeTorrentClient(),
        FakeSources(),
        FakeRepository(),
        Settings(
            qbittorrent_password="x",
            min_free_space_gb=0,
            torrent_storage_root="/tmp",
            torrent_save_path="/tmp/cache",
        ),
    )
    task = await manager.add(42, "movie", "a" * 24)

    with pytest.raises(TorrentFileError):
        await manager.select_file(task.id, 0)


async def test_existing_torrent_bypasses_new_download_limit() -> None:
    class LimitReachedClient(FakeTorrentClient):
        async def list(
            self, *, torrent_hash: str | None = None, tag: str | None = None
        ) -> list[dict[str, Any]]:
            if torrent_hash is None and tag is None:
                return [
                    {"hash": "first", "state": "downloading"},
                    {"hash": "second", "state": "downloading"},
                ]
            return await super().list(torrent_hash=torrent_hash, tag=tag)

        async def add(self, uri: str, tag: str) -> None:
            raise AssertionError("An existing torrent must not be added again")

    repository = FakeRepository()
    repository.tasks["existing-task"] = TorrentTask(
        id="existing-task",
        media_id=42,
        media_kind="movie",
        torrent_hash="abc123",
        source_id="a" * 24,
        release_title="Sintel",
        storage_path="/tmp/cache",
        state="stoppedUP",
    )
    manager = TorrentManager(
        LimitReachedClient(),
        FakeSources(),
        repository,
        Settings(
            qbittorrent_password="x",
            max_active_torrents=2,
            min_free_space_gb=0,
            torrent_storage_root="/tmp",
            torrent_save_path="/tmp/cache",
        ),
    )

    status = await manager.add(42, "movie", "a" * 24)

    assert status.id == "existing-task"


def test_active_download_limit_ignores_completed_seeding_torrents() -> None:
    assert not TorrentManager._is_active(
        {"state": "uploading", "progress": 1.0}
    )
    assert not TorrentManager._is_active(
        {"state": "stalledUP", "progress": 1.0}
    )
    assert TorrentManager._is_active(
        {"state": "downloading", "progress": 0.5}
    )
    assert TorrentManager._is_active(
        {"state": "queuedDL", "progress": 0.25}
    )
    assert TorrentManager._is_active(
        {"state": "stalledDL", "progress": 0.75}
    )
    assert not TorrentManager._is_active(
        {"state": "stoppedDL", "progress": 0.25}
    )


async def test_qbittorrent_client_authenticates_and_adds_stopped() -> None:
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/api/v2/auth/login":
            return httpx.Response(204, headers={"set-cookie": "SID=test"})
        return httpx.Response(200, text="Ok.")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://qbittorrent:8080"
    ) as http_client:
        client = QBittorrentClient(
            http_client,
            Settings(qbittorrent_username="kadr", qbittorrent_password="secret"),
        )
        await client.add("magnet:?xt=urn:btih:abc123", "kadr-task")
        await client.version()

    assert [call.url.path for call in calls] == [
        "/api/v2/auth/login",
        "/api/v2/torrents/add",
        "/api/v2/app/version",
    ]
    body = calls[1].content.decode()
    assert "stopCondition=MetadataReceived" in body
    assert "sequentialDownload=true" in body
    assert "firstLastPiecePrio=true" in body
    assert "stopped=true" not in body
    assert "magnet%3A" in body
    assert "secret" not in body


async def test_qbittorrent_client_enables_streaming_mode_idempotently() -> None:
    calls: list[httpx.Request] = []
    torrent_state = {"seq_dl": False, "f_l_piece_prio": False}

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/api/v2/auth/login":
            return httpx.Response(204, headers={"set-cookie": "SID=test"})
        if request.url.path == "/api/v2/torrents/info":
            return httpx.Response(200, json=[torrent_state])
        return httpx.Response(200, text="Ok.")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://qbittorrent:8080"
    ) as http_client:
        client = QBittorrentClient(
            http_client,
            Settings(qbittorrent_username="kadr", qbittorrent_password="secret"),
        )
        await client.prepare_for_streaming("abc123")
        torrent_state.update(seq_dl=True, f_l_piece_prio=True)
        await client.prepare_for_streaming("abc123")

    paths = [call.url.path for call in calls]
    assert paths.count("/api/v2/torrents/toggleSequentialDownload") == 1
    assert paths.count("/api/v2/torrents/toggleFirstLastPiecePrio") == 1
    assert paths.count("/api/v2/torrents/info") == 2


async def test_torrent_manager_rejects_save_path_outside_storage_root() -> None:
    manager = TorrentManager(
        FakeTorrentClient(),
        FakeSources(),
        FakeRepository(),
        Settings(
            qbittorrent_password="x",
            min_free_space_gb=0,
            torrent_storage_root="/tmp",
            torrent_save_path="/outside",
        ),
    )

    with pytest.raises(TorrentStorageError):
        await manager.add(42, "movie", "a" * 24)


async def test_torrent_api_exposes_lifecycle_without_source_uri(client: AsyncClient) -> None:
    manager = TorrentManager(
        FakeTorrentClient(),
        FakeSources(),
        FakeRepository(),
        Settings(
            qbittorrent_password="x",
            min_free_space_gb=0,
            torrent_storage_root="/tmp",
            torrent_save_path="/tmp/cache",
        ),
    )
    app.dependency_overrides[get_torrent_manager] = lambda: manager

    added = await client.post(
        "/api/v1/media/42/torrents",
        json={"media_kind": "movie", "source_id": "a" * 24},
    )
    assert added.status_code == 201
    assert "magnet" not in added.text.lower()
    task_id = added.json()["id"]

    current = await client.get("/api/v1/media/42/torrents?media_kind=movie")
    files = await client.get(f"/api/v1/torrents/{task_id}/files")
    selected = await client.put(f"/api/v1/torrents/{task_id}/selection", json={"file_id": 1})
    started = await client.post(f"/api/v1/torrents/{task_id}/start")
    stopped = await client.post(f"/api/v1/torrents/{task_id}/stop")

    assert current.status_code == 200
    assert current.json()["id"] == task_id
    assert files.status_code == 200
    assert files.json()[1]["is_video"] is True
    assert selected.json()["selected_file_path"] == "Sintel.mp4"
    assert started.json()["state"] == "downloading"
    assert stopped.json()["state"] == "stoppedDL"
