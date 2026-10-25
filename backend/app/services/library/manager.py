from __future__ import annotations

import asyncio
import errno
import os
import shutil
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.core.config import Settings
from app.models.library import Favorite, LibraryItem, WatchHistory
from app.repositories.library import LibraryRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.library import (
    FavoriteRequest,
    HistoryUpdateRequest,
    LibraryItemResponse,
    SaveLibraryItemRequest,
)
from app.services.library.exceptions import (
    LibraryConflictError,
    LibraryNotFoundError,
    LibraryStorageError,
)
from app.services.streaming.manager import media_type_for
from app.services.streaming.ranges import ByteRange, parse_byte_range
from app.services.streaming.registry import StreamLease, StreamRegistry
from app.services.torrents.qbittorrent import QBittorrentClient


@dataclass(frozen=True)
class LibraryStream:
    content: AsyncIterator[bytes]
    byte_range: ByteRange
    media_type: str
    filename: str
    release: Callable[[], Awaitable[None]]


class LibraryManager:
    def __init__(
        self,
        repository: LibraryRepository,
        tasks: TorrentTaskRepository,
        client: QBittorrentClient,
        registry: StreamRegistry,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._tasks = tasks
        self._client = client
        self._registry = registry
        self._settings = settings

    async def list(self) -> list[LibraryItemResponse]:
        return [self._response(item) for item in await self._repository.list_library()]

    async def save(self, body: SaveLibraryItemRequest) -> LibraryItemResponse:
        existing = await self._repository.get_library_by_media(body.media_id, body.media_kind)
        if existing is not None:
            return self._response(existing)
        task = await self._tasks.get(body.task_id)
        if task is None or task.media_id != body.media_id or task.media_kind != body.media_kind:
            raise LibraryNotFoundError("The selected torrent task does not belong to this media")
        if task.selected_file_id is None or task.selected_file_path is None:
            raise LibraryConflictError("Select a video file before saving it")
        files = await self._client.files(task.torrent_hash)
        selected = next(
            (
                item
                for index, item in enumerate(files)
                if int(item.get("index", index)) == task.selected_file_id
            ),
            None,
        )
        if selected is None or float(selected.get("progress") or 0) < 1:
            raise LibraryConflictError("The selected video must finish downloading before saving")
        source = self._safe_download(task.storage_path, task.selected_file_path)
        if not await asyncio.to_thread(source.is_file):
            raise LibraryStorageError("The downloaded video file is unavailable")
        target = self._library_target(body.media_kind, body.media_id, source.name)
        try:
            await asyncio.to_thread(self._materialize, source, target)
        except OSError as exc:
            raise LibraryStorageError("The video could not be written to the library") from exc
        item = LibraryItem(
            id=str(uuid.uuid4()),
            task_id=task.id,
            media_id=body.media_id,
            media_kind=body.media_kind,
            title=body.title,
            original_title=body.original_title,
            poster_url=body.poster_url,
            backdrop_url=body.backdrop_url,
            file_path=str(target),
            size_bytes=target.stat().st_size,
        )
        return self._response(await self._repository.add_library(item))

    async def delete(self, item_id: str) -> None:
        item = await self._repository.get_library(item_id)
        if item is None:
            raise LibraryNotFoundError("Library item not found")
        if await self._registry.is_active(f"library:{item.id}"):
            raise LibraryConflictError("Stop playback before deleting this saved video")
        path = self._safe_library_path(item.file_path)
        if await asyncio.to_thread(path.exists):
            await asyncio.to_thread(path.unlink)
            await asyncio.to_thread(self._remove_empty_parent, path.parent)
        await self._repository.delete_library(item)

    async def open(self, item_id: str, range_header: str | None) -> LibraryStream:
        item = await self._repository.get_library(item_id)
        if item is None:
            raise LibraryNotFoundError("Library item not found")
        path = self._safe_library_path(item.file_path)
        if not await asyncio.to_thread(path.is_file):
            raise LibraryStorageError("The saved video file is unavailable")
        size = path.stat().st_size
        byte_range = parse_byte_range(range_header, size)
        lease = await self._registry.acquire(f"library:{item.id}")
        return LibraryStream(
            content=self._read(path, byte_range, lease),
            byte_range=byte_range,
            media_type=media_type_for(path),
            filename=path.name,
            release=lease.release,
        )

    async def favorite(self, body: FavoriteRequest) -> Favorite:
        existing = await self._repository.get_favorite(body.media_id, body.media_kind)
        if existing is not None:
            return existing
        return await self._repository.add_favorite(
            Favorite(id=str(uuid.uuid4()), **body.model_dump())
        )

    async def list_favorites(self) -> list[Favorite]:
        return await self._repository.list_favorites()

    async def remove_favorite(self, media_id: int, media_kind: str) -> None:
        if not await self._repository.delete_favorite(media_id, media_kind):
            raise LibraryNotFoundError("Favorite not found")

    async def list_history(self) -> list[WatchHistory]:
        return await self._repository.list_history()

    async def get_history(self, media_id: int, media_kind: str) -> WatchHistory | None:
        return await self._repository.get_history(media_id, media_kind)

    async def history(self, media_id: int, body: HistoryUpdateRequest) -> WatchHistory:
        item = await self._repository.get_history(media_id, body.media_kind)
        if item is None:
            item = WatchHistory(id=str(uuid.uuid4()), media_id=media_id, **body.model_dump())
        else:
            for key, value in body.model_dump().items():
                setattr(item, key, value)
        return await self._repository.save_history(item)

    def _safe_download(self, storage_path: str, relative_path: str) -> Path:
        relative = PurePosixPath(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise LibraryStorageError("The selected video path is unsafe")
        root = Path(self._settings.torrent_storage_root).resolve(strict=True)
        storage = Path(storage_path).resolve(strict=False)
        source = (storage / Path(*relative.parts)).resolve(strict=False)
        if not storage.is_relative_to(root) or not source.is_relative_to(root):
            raise LibraryStorageError("The selected video is outside KADR storage")
        return source

    def _library_target(self, kind: str, media_id: int, filename: str) -> Path:
        root = Path(self._settings.library_root).resolve(strict=True)
        target = (
            root
            / ("movies" if kind == "movie" else "series")
            / str(media_id)
            / filename
        ).resolve(strict=False)
        if not target.is_relative_to(root):
            raise LibraryStorageError("The library target is outside KADR storage")
        return target

    def _safe_library_path(self, value: str) -> Path:
        root = Path(self._settings.library_root).resolve(strict=True)
        path = Path(value).resolve(strict=False)
        if not path.is_relative_to(root):
            raise LibraryStorageError("The saved video is outside KADR library storage")
        return path

    @staticmethod
    def _materialize(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.stat().st_size == source.stat().st_size:
            return
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            try:
                os.link(source, temporary)
            except OSError as exc:
                if exc.errno not in {errno.EXDEV, errno.EROFS, errno.EPERM, errno.EACCES}:
                    raise
                shutil.copy2(source, temporary)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def _remove_empty_parent(self, directory: Path) -> None:
        root = Path(self._settings.library_root).resolve(strict=True)
        if directory != root and directory.is_relative_to(root):
            try:
                directory.rmdir()
            except OSError:
                pass

    async def _read(
        self,
        path: Path,
        byte_range: ByteRange,
        lease: StreamLease,
    ) -> AsyncIterator[bytes]:
        file = None
        remaining = byte_range.length
        try:
            file = await asyncio.to_thread(path.open, "rb")
            await asyncio.to_thread(file.seek, byte_range.start)
            while remaining:
                chunk = await asyncio.to_thread(file.read, min(1024 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
        finally:
            if file is not None:
                await asyncio.to_thread(file.close)
            await lease.release()

    @staticmethod
    def _response(item: LibraryItem) -> LibraryItemResponse:
        return LibraryItemResponse(
            id=item.id,
            task_id=item.task_id,
            media_id=item.media_id,
            media_kind=item.media_kind,  # type: ignore[arg-type]
            title=item.title,
            original_title=item.original_title,
            poster_url=item.poster_url,
            backdrop_url=item.backdrop_url,
            size_bytes=item.size_bytes,
            created_at=item.created_at,
            stream_url=f"/api/v1/library/{item.id}/stream",
        )
