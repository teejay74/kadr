import asyncio
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

from app.core.config import Settings
from app.repositories.library import LibraryRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.library import (
    CacheCleanupResponse,
    CacheFileDeletionResponse,
    StorageResponse,
)
from app.services.cache.exceptions import (
    CacheDeletionConflictError,
    CacheFileNotFoundError,
    CacheStorageError,
)
from app.services.playback.manager import CompatibilityManager
from app.services.streaming.registry import StreamRegistry
from app.services.torrents.manager import VIDEO_EXTENSIONS
from app.services.torrents.qbittorrent import QBittorrentClient


class CacheManager:
    def __init__(
        self,
        tasks: TorrentTaskRepository,
        library: LibraryRepository,
        client: QBittorrentClient,
        registry: StreamRegistry,
        compatibility: CompatibilityManager,
        settings: Settings,
    ) -> None:
        self._tasks = tasks
        self._library = library
        self._client = client
        self._registry = registry
        self._compatibility = compatibility
        self._settings = settings

    async def delete_file(self, task_id: str, file_id: int) -> CacheFileDeletionResponse:
        task = await self._tasks.get(task_id)
        if task is None:
            raise CacheFileNotFoundError("Torrent task not found")
        if await self._registry.is_active(task.id):
            raise CacheDeletionConflictError("Close the player before deleting this video")
        if self._compatibility.is_preparing(task.id, file_id):
            raise CacheDeletionConflictError(
                "Wait for compatible video preparation to finish before deleting"
            )
        saved = await self._library.get_library_by_media(task.media_id, task.media_kind)
        if saved is not None and saved.task_id == task.id:
            raise CacheDeletionConflictError(
                "This download belongs to a saved library item and is protected"
            )

        files = await self._client.files(task.torrent_hash)
        if file_id < 0 or file_id >= len(files):
            raise CacheFileNotFoundError("Downloaded video not found")
        item = files[file_id]
        relative = PurePosixPath(str(item.get("name") or ""))
        if relative.suffix.lower() not in VIDEO_EXTENSIONS:
            raise CacheDeletionConflictError("Only video files can be deleted here")
        if float(item.get("progress") or 0) < 1:
            raise CacheDeletionConflictError("Only a fully downloaded video can be deleted")
        storage, path = self._safe_cache_file(task.storage_path, relative)
        if not await asyncio.to_thread(path.is_file):
            raise CacheFileNotFoundError("Downloaded video file is unavailable")

        torrents = await self._client.list(torrent_hash=task.torrent_hash)
        was_active = bool(torrents) and str(torrents[0].get("state") or "") not in {
            "pausedDL",
            "pausedUP",
            "stoppedDL",
            "stoppedUP",
            "error",
            "missingFiles",
        }
        await self._client.stop(task.torrent_hash)
        await self._client.set_file_priority(task.torrent_hash, [file_id], 0)
        try:
            await self._compatibility.discard(task.id, file_id)
            reclaimed = (await asyncio.to_thread(path.stat)).st_size
            await asyncio.to_thread(path.unlink)
            await asyncio.to_thread(
                self._remove_empty_cache_parents,
                path.parent,
                storage,
            )
        except OSError as exc:
            raise CacheStorageError("The downloaded video could not be deleted") from exc

        selected_cleared = task.selected_file_id == file_id
        if selected_cleared:
            await self._tasks.clear_selection(task)
        await self._client.recheck(task.torrent_hash)
        if was_active:
            await self._client.start(task.torrent_hash)
        return CacheFileDeletionResponse(
            task_id=task.id,
            file_id=file_id,
            reclaimed_bytes=reclaimed,
            selected_file_cleared=selected_cleared,
        )

    async def cleanup(self) -> CacheCleanupResponse:
        cutoff = datetime.now(UTC) - timedelta(hours=self._settings.cache_ttl_hours)
        removed = 0
        reclaimed = 0
        for task in await self._tasks.list_older_than(cutoff):
            if await self._registry.is_active(task.id):
                continue
            saved = await self._library.get_library_by_media(task.media_id, task.media_kind)
            if saved is not None and saved.task_id == task.id:
                continue
            items = await self._client.list(torrent_hash=task.torrent_hash)
            if items:
                item = items[0]
                if str(item.get("state") or "") not in {
                    "pausedDL", "pausedUP", "stoppedDL", "stoppedUP", "error", "missingFiles"
                }:
                    continue
                reclaimed += max(int(item.get("downloaded") or 0), 0)
                await self._client.delete(task.torrent_hash, delete_files=True)
            await self._tasks.delete(task)
            removed += 1
        return CacheCleanupResponse(removed_tasks=removed, reclaimed_bytes=reclaimed)

    async def storage(self) -> StorageResponse:
        library_items, library_bytes = await self._library.library_totals()
        torrents = await self._client.list()
        cache_bytes = sum(max(int(item.get("downloaded") or 0), 0) for item in torrents)
        root = Path(self._settings.library_root).resolve(strict=True)
        usage = await asyncio.to_thread(shutil.disk_usage, root)
        return StorageResponse(
            library_bytes=library_bytes,
            library_items=library_items,
            cache_bytes=cache_bytes,
            cache_tasks=len(torrents),
            free_bytes=usage.free,
        )

    def _safe_cache_file(
        self,
        storage_path: str,
        relative: PurePosixPath,
    ) -> tuple[Path, Path]:
        if relative.is_absolute() or ".." in relative.parts:
            raise CacheStorageError("The downloaded video path is unsafe")
        try:
            root = Path(self._settings.torrent_storage_root).resolve(strict=True)
            storage = Path(storage_path).resolve(strict=True)
            path = (storage / Path(*relative.parts)).resolve(strict=False)
        except OSError as exc:
            raise CacheStorageError("KADR download storage is unavailable") from exc
        if not storage.is_relative_to(root) or not path.is_relative_to(storage):
            raise CacheStorageError("The downloaded video is outside KADR cache")
        return storage, path

    def _remove_empty_cache_parents(self, directory: Path, storage: Path) -> None:
        root = Path(self._settings.torrent_storage_root).resolve(strict=True)
        current = directory
        while current != storage and current != root and current.is_relative_to(storage):
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
