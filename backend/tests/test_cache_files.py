from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.library import LibraryItem
from app.models.torrent_task import TorrentTask
from app.repositories.library import LibraryRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.services.cache.exceptions import (
    CacheDeletionConflictError,
    CacheStorageError,
)
from app.services.cache.manager import CacheManager
from app.services.playback.manager import CompatibilityManager
from app.services.streaming.registry import StreamRegistry


class FakeQBittorrent:
    def __init__(self, files: list[dict[str, Any]], state: str = "downloading") -> None:
        self._files = files
        self.state = state
        self.calls: list[tuple[object, ...]] = []

    async def files(self, _: str) -> list[dict[str, Any]]:
        return self._files

    async def list(
        self,
        *,
        torrent_hash: str | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        del torrent_hash, tag
        return [{"state": self.state}]

    async def stop(self, torrent_hash: str) -> None:
        self.calls.append(("stop", torrent_hash))

    async def start(self, torrent_hash: str) -> None:
        self.calls.append(("start", torrent_hash))

    async def recheck(self, torrent_hash: str) -> None:
        self.calls.append(("recheck", torrent_hash))

    async def set_file_priority(
        self,
        torrent_hash: str,
        file_ids: list[int],
        priority: int,
    ) -> None:
        self.calls.append(("priority", torrent_hash, file_ids, priority))


async def make_cache_manager(
    session: AsyncSession,
    tmp_path: Path,
    *,
    filename: str = "Season/S01E03.mkv",
    progress: float = 1.0,
) -> tuple[CacheManager, FakeQBittorrent, TorrentTask, Path, StreamRegistry]:
    downloads = tmp_path / "downloads"
    storage = downloads / "cache" / "task-id"
    library = tmp_path / "library"
    playback = tmp_path / "playback"
    path = storage / filename
    path.parent.mkdir(parents=True)
    path.write_bytes(b"episode")
    library.mkdir()
    settings = Settings(
        torrent_storage_root=str(downloads),
        torrent_save_path=str(downloads / "cache"),
        library_root=str(library),
        playback_cache_root=str(playback),
        min_free_space_gb=0,
    )
    task = TorrentTask(
        id="00000000-0000-0000-0000-000000000003",
        media_id=288673,
        media_kind="series",
        torrent_hash="torrent-hash",
        source_id="source",
        release_title="Series",
        selected_file_id=0,
        selected_file_path=filename,
        storage_path=str(storage),
        state="downloading",
    )
    await TorrentTaskRepository(session).create(task)
    client = FakeQBittorrent(
        [{"index": 0, "name": filename, "progress": progress, "size": 7}]
    )
    registry = StreamRegistry(2)
    manager = CacheManager(
        TorrentTaskRepository(session),
        LibraryRepository(session),
        client,  # type: ignore[arg-type]
        registry,
        CompatibilityManager(settings),
        settings,
    )
    return manager, client, task, path, registry


@pytest.mark.asyncio
async def test_delete_downloaded_episode_and_clear_current_selection(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    manager, client, task, path, _ = await make_cache_manager(session, tmp_path)

    result = await manager.delete_file(task.id, 0)

    assert not path.exists()
    assert result.reclaimed_bytes == 7
    assert result.selected_file_cleared is True
    assert task.selected_file_id is None
    assert task.selected_file_path is None
    assert client.calls == [
        ("stop", "torrent-hash"),
        ("priority", "torrent-hash", [0], 0),
        ("recheck", "torrent-hash"),
        ("start", "torrent-hash"),
    ]


@pytest.mark.asyncio
async def test_delete_downloaded_episode_is_blocked_during_stream(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    manager, client, task, path, registry = await make_cache_manager(session, tmp_path)
    lease = await registry.acquire(task.id)

    with pytest.raises(CacheDeletionConflictError):
        await manager.delete_file(task.id, 0)

    assert path.exists()
    assert client.calls == []
    await lease.release()


@pytest.mark.asyncio
async def test_delete_downloaded_episode_is_blocked_for_saved_media(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    manager, client, task, path, _ = await make_cache_manager(session, tmp_path)
    await LibraryRepository(session).add_library(
        LibraryItem(
            id="00000000-0000-0000-0000-000000000004",
            task_id=task.id,
            media_id=task.media_id,
            media_kind=task.media_kind,
            title="Series",
            original_title="",
            poster_url=None,
            backdrop_url=None,
            file_path=str(path),
            size_bytes=path.stat().st_size,
        )
    )

    with pytest.raises(CacheDeletionConflictError):
        await manager.delete_file(task.id, 0)

    assert path.exists()
    assert client.calls == []


@pytest.mark.asyncio
async def test_delete_downloaded_episode_rejects_path_escape(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    manager, client, task, path, _ = await make_cache_manager(
        session,
        tmp_path,
        filename="episode.mkv",
    )
    outside = tmp_path / "outside.mkv"
    outside.write_bytes(b"outside")
    client._files[0]["name"] = "../../../outside.mkv"

    with pytest.raises(CacheStorageError):
        await manager.delete_file(task.id, 0)

    assert path.exists()
    assert outside.exists()
    assert client.calls == []


@pytest.mark.asyncio
async def test_delete_downloaded_episode_requires_complete_file(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    manager, client, task, path, _ = await make_cache_manager(
        session,
        tmp_path,
        progress=0.5,
    )

    with pytest.raises(CacheDeletionConflictError):
        await manager.delete_file(task.id, 0)

    assert path.exists()
    assert client.calls == []
