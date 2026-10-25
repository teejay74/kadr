from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.library import LibraryItem
from app.models.torrent_task import TorrentTask
from app.repositories.library import LibraryRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.library import FavoriteRequest, HistoryUpdateRequest, SaveLibraryItemRequest
from app.services.cache.manager import CacheManager
from app.services.library.exceptions import LibraryConflictError, LibraryStorageError
from app.services.library.manager import LibraryManager
from app.services.streaming.registry import StreamRegistry


class FakeQBittorrent:
    def __init__(self, progress: float = 1.0) -> None:
        self.progress = progress
        self.deleted: list[tuple[str, bool]] = []

    async def files(self, _: str) -> list[dict[str, Any]]:
        return [{"index": 0, "name": "video.mp4", "progress": self.progress, "size": 8}]

    async def list(
        self,
        *,
        torrent_hash: str | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        del torrent_hash, tag
        return [{"state": "stoppedUP", "downloaded": 8}]

    async def delete(self, torrent_hash: str, *, delete_files: bool) -> None:
        self.deleted.append((torrent_hash, delete_files))


async def make_manager(
    session: AsyncSession,
    tmp_path: Path,
    *,
    progress: float = 1.0,
) -> tuple[LibraryManager, FakeQBittorrent, TorrentTask]:
    downloads = tmp_path / "downloads"
    cache = downloads / "cache"
    library = tmp_path / "library"
    cache.mkdir(parents=True)
    library.mkdir()
    (cache / "video.mp4").write_bytes(b"abcdefgh")
    settings = Settings(
        torrent_storage_root=str(downloads),
        torrent_save_path=str(cache),
        library_root=str(library),
        min_free_space_gb=0,
    )
    task = TorrentTask(
        id="00000000-0000-0000-0000-000000000001",
        media_id=42,
        media_kind="movie",
        torrent_hash="abc123",
        source_id="source",
        release_title="Example",
        selected_file_id=0,
        selected_file_path="video.mp4",
        storage_path=str(cache),
        state="stoppedUP",
    )
    await TorrentTaskRepository(session).create(task)
    client = FakeQBittorrent(progress)
    manager = LibraryManager(
        LibraryRepository(session),
        TorrentTaskRepository(session),
        client,  # type: ignore[arg-type]
        StreamRegistry(2),
        settings,
    )
    return manager, client, task


@pytest.mark.asyncio
async def test_save_stream_and_delete_library_item(session: AsyncSession, tmp_path: Path) -> None:
    manager, _, task = await make_manager(session, tmp_path)
    saved = await manager.save(
        SaveLibraryItemRequest(
            task_id=task.id,
            media_id=42,
            media_kind="movie",
            title="Example",
        )
    )

    stream = await manager.open(saved.id, "bytes=2-5")
    assert b"".join([chunk async for chunk in stream.content]) == b"cdef"
    assert stream.byte_range.length == 4
    await manager.delete(saved.id)
    assert await manager.list() == []


@pytest.mark.asyncio
async def test_save_requires_complete_selected_file(session: AsyncSession, tmp_path: Path) -> None:
    manager, _, task = await make_manager(session, tmp_path, progress=0.5)
    with pytest.raises(LibraryConflictError):
        await manager.save(
            SaveLibraryItemRequest(
                task_id=task.id,
                media_id=42,
                media_kind="movie",
                title="Example",
            )
        )


@pytest.mark.asyncio
async def test_library_rejects_paths_outside_kadr_storage(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    manager, _, task = await make_manager(session, tmp_path)
    task.selected_file_path = "../outside.mp4"
    await session.commit()
    with pytest.raises(LibraryStorageError):
        await manager.save(
            SaveLibraryItemRequest(
                task_id=task.id,
                media_id=42,
                media_kind="movie",
                title="Example",
            )
        )


@pytest.mark.asyncio
async def test_favorites_and_history_are_persistent(session: AsyncSession, tmp_path: Path) -> None:
    manager, _, _ = await make_manager(session, tmp_path)
    await manager.favorite(
        FavoriteRequest(media_id=42, media_kind="movie", title="Example")
    )
    history = await manager.history(
        42,
        HistoryUpdateRequest(
            media_kind="movie",
            title="Example",
            position_seconds=120,
            duration_seconds=3600,
        ),
    )
    assert len(await manager.list_favorites()) == 1
    assert history.position_seconds == 120
    assert (await manager.get_history(42, "movie")).position_seconds == 120  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_cache_cleanup_protects_saved_items(session: AsyncSession, tmp_path: Path) -> None:
    manager, client, task = await make_manager(session, tmp_path)
    saved = await manager.save(
        SaveLibraryItemRequest(
            task_id=task.id,
            media_id=42,
            media_kind="movie",
            title="Example",
        )
    )
    item = await LibraryRepository(session).get_library(saved.id)
    assert isinstance(item, LibraryItem)
    task.updated_at = datetime.now(UTC) - timedelta(hours=48)
    await session.commit()
    cache = CacheManager(
        TorrentTaskRepository(session),
        LibraryRepository(session),
        client,  # type: ignore[arg-type]
        StreamRegistry(2),
        Settings(cache_ttl_hours=24),
    )
    result = await cache.cleanup()
    assert result.removed_tasks == 0
    assert client.deleted == []


@pytest.mark.asyncio
async def test_active_library_stream_cannot_be_deleted(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    manager, _, task = await make_manager(session, tmp_path)
    saved = await manager.save(
        SaveLibraryItemRequest(
            task_id=task.id,
            media_id=42,
            media_kind="movie",
            title="Example",
        )
    )
    stream = await manager.open(saved.id, "bytes=0-1")
    with pytest.raises(LibraryConflictError):
        await manager.delete(saved.id)
    await stream.release()


@pytest.mark.asyncio
async def test_cache_cleanup_removes_only_expired_stopped_unsaved_task(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    _, client, task = await make_manager(session, tmp_path)
    task.updated_at = datetime.now(UTC) - timedelta(hours=48)
    await session.commit()
    cache = CacheManager(
        TorrentTaskRepository(session),
        LibraryRepository(session),
        client,  # type: ignore[arg-type]
        StreamRegistry(2),
        Settings(cache_ttl_hours=24),
    )
    result = await cache.cleanup()
    assert result.removed_tasks == 1
    assert result.reclaimed_bytes == 8
    assert client.deleted == [("abc123", True)]
    assert await TorrentTaskRepository(session).get(task.id) is None
