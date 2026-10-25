import asyncio
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import Settings
from app.repositories.library import LibraryRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.library import CacheCleanupResponse, StorageResponse
from app.services.streaming.registry import StreamRegistry
from app.services.torrents.qbittorrent import QBittorrentClient


class CacheManager:
    def __init__(
        self,
        tasks: TorrentTaskRepository,
        library: LibraryRepository,
        client: QBittorrentClient,
        registry: StreamRegistry,
        settings: Settings,
    ) -> None:
        self._tasks = tasks
        self._library = library
        self._client = client
        self._registry = registry
        self._settings = settings

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
