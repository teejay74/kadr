from __future__ import annotations

import asyncio
import logging
import mimetypes
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from app.core.config import Settings
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.torrents import StreamReadiness
from app.services.streaming.exceptions import (
    StreamBufferTimeoutError,
    StreamNotReadyError,
)
from app.services.streaming.ranges import ByteRange, parse_byte_range
from app.services.streaming.registry import StreamLease, StreamRegistry
from app.services.torrents.manager import TorrentManager
from app.services.torrents.qbittorrent import QBittorrentClient

logger = logging.getLogger(__name__)

VIDEO_MEDIA_TYPES = {
    ".avi": "video/x-msvideo",
    ".m2ts": "video/mp2t",
    ".m4v": "video/x-m4v",
    ".mkv": "video/x-matroska",
    ".mov": "video/quicktime",
    ".mp4": "video/mp4",
    ".mpeg": "video/mpeg",
    ".mpg": "video/mpeg",
    ".ts": "video/mp2t",
    ".webm": "video/webm",
}


def media_type_for(path: Path) -> str:
    return VIDEO_MEDIA_TYPES.get(
        path.suffix.lower(),
        mimetypes.guess_type(path.name)[0] or "application/octet-stream",
    )


@dataclass(frozen=True)
class PreparedStream:
    content: AsyncIterator[bytes]
    byte_range: ByteRange
    media_type: str
    filename: str
    release: Callable[[], Awaitable[None]]


class PieceAvailability:
    def __init__(
        self,
        client: QBittorrentClient,
        torrent_hash: str,
        piece_size: int,
        file_offset: int,
        settings: Settings,
    ) -> None:
        self._client = client
        self._torrent_hash = torrent_hash
        self._piece_size = piece_size
        self._file_offset = file_offset
        self._timeout = settings.stream_read_timeout_seconds
        self._poll_interval = settings.stream_poll_interval_seconds
        self._states: list[int] = []
        self._refreshed_at = 0.0

    async def wait_for(self, start: int, end: int) -> None:
        first_piece = (self._file_offset + start) // self._piece_size
        last_piece = (self._file_offset + end) // self._piece_size
        deadline = time.monotonic() + self._timeout
        while True:
            now = time.monotonic()
            if not self._states or now - self._refreshed_at >= self._poll_interval:
                self._states = await self._client.piece_states(self._torrent_hash)
                self._refreshed_at = now
            if last_piece < len(self._states) and all(
                state == 2 for state in self._states[first_piece : last_piece + 1]
            ):
                return
            if now >= deadline:
                raise StreamBufferTimeoutError(
                    "The requested video data did not arrive before the stream timeout"
                )
            await asyncio.sleep(min(self._poll_interval, max(deadline - now, 0)))


class StreamingManager:
    def __init__(
        self,
        client: QBittorrentClient,
        torrents: TorrentManager,
        repository: TorrentTaskRepository,
        registry: StreamRegistry,
        settings: Settings,
    ) -> None:
        self._client = client
        self._torrents = torrents
        self._repository = repository
        self._registry = registry
        self._settings = settings

    async def readiness(self, task_id: str) -> StreamReadiness:
        task = await self._repository.get(task_id)
        if (
            task is None
            or task.selected_file_id is None
            or task.selected_file_path is None
        ):
            raise StreamNotReadyError("Select a video file before starting playback")

        files = await self._client.files(task.torrent_hash)
        selected, ordered = self._selected_file(files, task.selected_file_id)
        size = max(int(selected.get("size") or 0), 0)
        if size <= 0:
            raise StreamNotReadyError("The selected video size is not available")
        properties = await self._client.properties(task.torrent_hash)
        piece_size = int(properties.get("piece_size") or 0)
        if piece_size <= 0:
            raise StreamNotReadyError("Torrent piece information is not available")
        file_offset = sum(
            max(int(item.get("size") or 0), 0)
            for item in ordered
            if int(item.get("index", 0)) < task.selected_file_id
        )

        await self._client.set_file_priority(
            task.torrent_hash, [task.selected_file_id], 1
        )
        speed = 0
        if float(selected.get("progress") or 0) < 1:
            await self._client.prepare_for_streaming(task.torrent_hash)
            status = await self._torrents.start(task_id)
            speed = status.download_speed_bytes

        states = await self._client.piece_states(task.torrent_hash)
        initial_bytes = self._initial_buffer_bytes(size, speed)
        required = self._required_probe_pieces(
            size,
            piece_size,
            file_offset,
            initial_bytes,
        )
        completed = sum(
            index < len(states) and states[index] == 2 for index in required
        )
        path = self._safe_file_path(task.storage_path, task.selected_file_path)
        file_exists = await asyncio.to_thread(path.is_file)
        progress = completed / len(required) if required else 0.0
        return StreamReadiness(
            ready=file_exists and completed == len(required),
            buffer_progress=progress,
        )

    async def open(self, task_id: str, range_header: str | None) -> PreparedStream:
        task = await self._repository.get(task_id)
        if task is None or task.selected_file_id is None or task.selected_file_path is None:
            raise StreamNotReadyError("Select a video file before starting playback")

        files = await self._client.files(task.torrent_hash)
        selected, ordered = self._selected_file(files, task.selected_file_id)
        size = max(int(selected.get("size") or 0), 0)
        if size <= 0:
            raise StreamNotReadyError("The selected video size is not available")
        byte_range = parse_byte_range(range_header, size)
        path = self._safe_file_path(task.storage_path, task.selected_file_path)
        properties = await self._client.properties(task.torrent_hash)
        piece_size = int(properties.get("piece_size") or 0)
        if piece_size <= 0:
            raise StreamNotReadyError("Torrent piece information is not available")
        file_offset = sum(
            max(int(item.get("size") or 0), 0)
            for item in ordered
            if int(item.get("index", 0)) < task.selected_file_id
        )

        lease = await self._registry.acquire(task_id)
        try:
            await self._client.set_file_priority(
                task.torrent_hash, [task.selected_file_id], 1
            )
            status = None
            if float(selected.get("progress") or 0) < 1:
                await self._client.prepare_for_streaming(task.torrent_hash)
                status = await self._torrents.start(task_id)
            speed = status.download_speed_bytes if status is not None else 0
            checker = PieceAvailability(
                self._client,
                task.torrent_hash,
                piece_size,
                file_offset,
                self._settings,
            )
            initial_bytes = self._initial_buffer_bytes(byte_range.length, speed)
            await checker.wait_for(
                byte_range.start,
                byte_range.start + initial_bytes - 1,
            )
            await self._wait_for_file(path)
        except Exception:
            await lease.release()
            raise

        return PreparedStream(
            content=self._read(path, byte_range, checker, lease),
            byte_range=byte_range,
            media_type=media_type_for(path),
            filename=PurePosixPath(task.selected_file_path).name,
            release=lease.release,
        )

    @staticmethod
    def _selected_file(
        files: list[dict[str, Any]], selected_file_id: int
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        ordered = sorted(
            (
                {**item, "index": int(item.get("index", index))}
                for index, item in enumerate(files)
            ),
            key=lambda item: int(item["index"]),
        )
        selected = next(
            (item for item in ordered if int(item["index"]) == selected_file_id),
            None,
        )
        if selected is None:
            raise StreamNotReadyError("The selected video is no longer in the torrent")
        return selected, ordered

    def _safe_file_path(self, storage_path: str, relative_path: str) -> Path:
        relative = PurePosixPath(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise StreamNotReadyError("The selected video path is unsafe")
        try:
            root = Path(self._settings.torrent_storage_root).resolve(strict=True)
            storage = Path(storage_path).resolve(strict=False)
            candidate = (storage / Path(*relative.parts)).resolve(strict=False)
        except OSError as exc:
            raise StreamNotReadyError("The download storage is unavailable") from exc
        if not storage.is_relative_to(root) or not candidate.is_relative_to(root):
            raise StreamNotReadyError("The selected video is outside KADR storage")
        return candidate

    def _initial_buffer_bytes(self, range_length: int, download_speed: int) -> int:
        configured = self._settings.stream_start_buffer_mb * 1024**2
        chunk_size = self._settings.stream_chunk_size_kb * 1024
        adaptive = min(max(download_speed, 0) * 4, configured)
        return min(range_length, max(adaptive, chunk_size))

    def _required_probe_pieces(
        self,
        file_size: int,
        piece_size: int,
        file_offset: int,
        initial_bytes: int,
    ) -> set[int]:
        tail_bytes = min(
            file_size,
            max(self._settings.stream_chunk_size_kb * 4096, 4 * 1024**2),
        )

        def pieces(start: int, end: int) -> range:
            first = (file_offset + start) // piece_size
            last = (file_offset + end) // piece_size
            return range(first, last + 1)

        required = set(pieces(0, initial_bytes - 1))
        required.update(pieces(file_size - tail_bytes, file_size - 1))
        return required

    async def _wait_for_file(self, path: Path) -> None:
        deadline = time.monotonic() + self._settings.stream_read_timeout_seconds
        while True:
            if await asyncio.to_thread(path.is_file):
                return
            if time.monotonic() >= deadline:
                raise StreamBufferTimeoutError("The selected video file is not available")
            await asyncio.sleep(self._settings.stream_poll_interval_seconds)

    async def _read(
        self,
        path: Path,
        byte_range: ByteRange,
        checker: PieceAvailability,
        lease: StreamLease,
    ) -> AsyncIterator[bytes]:
        file = None
        offset = byte_range.start
        chunk_size = self._settings.stream_chunk_size_kb * 1024
        try:
            file = await asyncio.to_thread(path.open, "rb")
            await asyncio.to_thread(file.seek, byte_range.start)
            while offset <= byte_range.end:
                length = min(chunk_size, byte_range.end - offset + 1)
                await checker.wait_for(offset, offset + length - 1)
                chunk = await asyncio.to_thread(file.read, length)
                if len(chunk) != length:
                    raise StreamBufferTimeoutError(
                        "The selected video file ended before the requested range"
                    )
                offset += len(chunk)
                yield chunk
        except asyncio.CancelledError:
            logger.info("Streaming client disconnected", extra={"task_id": "redacted"})
            raise
        finally:
            if file is not None:
                await asyncio.to_thread(file.close)
            await lease.release()
