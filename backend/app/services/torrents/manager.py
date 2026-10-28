from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from app.core.config import Settings
from app.models.torrent_task import TorrentTask
from app.repositories.episodes import EpisodeRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.media import MediaKind
from app.schemas.torrents import EpisodeFileBindingResponse, TorrentFile, TorrentStatus
from app.services.sources.search import SourceSearchService
from app.services.torrents.exceptions import (
    TorrentFileError,
    TorrentLimitError,
    TorrentNotFoundError,
    TorrentStorageError,
    TorrentUnavailableError,
)
from app.services.torrents.qbittorrent import QBittorrentClient

VIDEO_EXTENSIONS = {
    ".avi",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ts",
    ".webm",
}
STOPPED_STATES = {"pausedDL", "pausedUP", "stoppedDL", "stoppedUP", "error", "missingFiles"}


class TorrentManager:
    def __init__(
        self,
        client: QBittorrentClient,
        sources: SourceSearchService,
        repository: TorrentTaskRepository,
        settings: Settings,
        episodes: EpisodeRepository | None = None,
    ) -> None:
        self._client = client
        self._sources = sources
        self._repository = repository
        self._settings = settings
        self._episodes = episodes

    async def add(
        self,
        media_id: int,
        media_kind: MediaKind,
        source_id: str,
        season_number: int | None = None,
    ) -> TorrentStatus:
        source = await self._sources.resolve(
            media_id,
            media_kind,
            source_id,
            season_number,
        )
        if source is None:
            raise TorrentNotFoundError("The selected source is no longer available")
        existing_source = await self._repository.get_latest_by_source(
            media_id,
            media_kind,
            source_id,
        )
        if existing_source is not None:
            try:
                return await self.status(existing_source.id)
            except TorrentNotFoundError:
                # The database can outlive a manually removed qBittorrent item.
                # In that case, continue with a fresh add instead of restoring
                # the stale task.
                pass
        known_hash = (source.info_hash or "").lower()
        if known_hash:
            existing = await self._repository.get_by_hash(known_hash)
            if existing is not None:
                return await self.status(existing.id)
        await self._ensure_free_space()
        active = [item for item in await self._client.list() if self._is_active(item)]
        if len(active) >= self._settings.max_active_torrents:
            raise TorrentLimitError("The active torrent limit has been reached")
        task_id = str(uuid.uuid4())
        tag = f"kadr-{task_id}"
        await self._client.add(source.uri, tag)
        torrent = await self._wait_for_torrent(known_hash, tag)
        torrent_hash = str(torrent.get("hash") or "").lower()
        if not torrent_hash:
            raise TorrentUnavailableError("qBittorrent did not return a torrent hash")
        existing = await self._repository.get_by_hash(torrent_hash)
        if existing is not None:
            return await self.status(existing.id)
        task = TorrentTask(
            id=task_id,
            media_id=media_id,
            media_kind=media_kind,
            torrent_hash=torrent_hash,
            source_id=source_id,
            release_title=source.release.title,
            storage_path=self._settings.torrent_save_path,
            state=str(torrent.get("state") or "unknown"),
        )
        await self._repository.create(task)
        return self._to_status(task, torrent)

    async def status(self, task_id: str) -> TorrentStatus:
        task = await self._task(task_id)
        items = await self._client.list(torrent_hash=task.torrent_hash)
        if not items:
            raise TorrentNotFoundError("The torrent is no longer present in qBittorrent")
        state = str(items[0].get("state") or "unknown")
        await self._repository.set_state(task, state)
        return self._to_status(task, items[0])

    async def current(self, media_id: int, media_kind: MediaKind) -> TorrentStatus:
        task = await self._repository.get_latest_by_media(media_id, media_kind)
        if task is None:
            raise TorrentNotFoundError("Torrent task not found")
        return await self.status(task.id)

    async def list_tasks(self) -> list[TorrentStatus]:
        """Return recent KADR tasks using one bounded qBittorrent request."""
        tasks = await self._repository.list_recent()
        if not tasks:
            return []
        items = await self._client.list()
        by_hash = {
            str(item.get("hash") or "").lower(): item
            for item in items
            if item.get("hash")
        }
        return [
            self._to_status(
                task,
                by_hash.get(
                    task.torrent_hash.lower(),
                    {"state": "unavailable"},
                ),
            )
            for task in tasks
        ]

    async def files(self, task_id: str) -> list[TorrentFile]:
        task = await self._task(task_id)
        items = await self._client.files(task.torrent_hash)
        if items and task.selected_file_id is None:
            await self._client.set_file_priority(task.torrent_hash, list(range(len(items))), 0)
            items = await self._client.files(task.torrent_hash)
        return [self._to_file(index, item) for index, item in enumerate(items)]

    async def select_file(
        self,
        task_id: str,
        file_id: int,
        season_number: int | None = None,
        episode_number: int | None = None,
        catalog_episode_id: int | None = None,
        variant_label: str | None = None,
    ) -> TorrentStatus:
        task = await self._task(task_id)
        files = await self._client.files(task.torrent_hash)
        if file_id >= len(files):
            raise TorrentFileError("The selected torrent file does not exist")
        selected = self._to_file(file_id, files[file_id])
        if not selected.is_video:
            raise TorrentFileError("Only a supported video file can be selected")
        if not self._safe_relative_path(selected.name):
            raise TorrentFileError("The selected torrent file has an unsafe path")
        preserved_prefetch_ids = []
        if task.selected_file_id is not None:
            preserved_prefetch_ids = [
                index
                for index, item in enumerate(files)
                if index > file_id
                and int(item.get("priority") or 0) > 0
                and self._to_file(index, item).is_video
            ]
        await self._client.set_file_priority(
            task.torrent_hash,
            list(range(len(files))),
            0,
        )
        # qBittorrent 5.x can abandon sequential piece ordering when the only
        # selected file has maximal priority. Normal priority keeps skipped
        # files disabled while allowing the sequential picker to start at the
        # beginning of the selected video.
        await self._client.set_file_priority(
            task.torrent_hash,
            sorted({file_id, *preserved_prefetch_ids}),
            1,
        )
        await self._repository.select_file(task, file_id, selected.name)
        if season_number is not None and episode_number is not None:
            if task.media_kind != "series":
                raise TorrentFileError("Episode identity can only be assigned to a series")
            if self._episodes is None:
                raise TorrentFileError("Episode persistence is unavailable")
            await self._episodes.bind_file(
                task,
                file_id,
                selected.name,
                season_number,
                episode_number,
                catalog_episode_id,
                variant_label,
            )
        return await self.status(task_id)

    async def select_preferred_movie_file(self, task_id: str) -> TorrentStatus:
        """Select the largest safe video for a film when no legacy choice exists."""
        task = await self._task(task_id)
        if task.media_kind != "movie":
            raise TorrentFileError("Automatic movie selection is unavailable for series")
        if task.selected_file_id is not None:
            return await self.status(task_id)
        files = await self._client.files(task.torrent_hash)
        candidates: list[TorrentFile] = []
        for index, item in enumerate(files):
            candidate = self._to_file(index, item)
            if candidate.is_video and self._safe_relative_path(candidate.name):
                candidates.append(candidate)
        if not candidates:
            raise TorrentFileError("The torrent does not contain a safe supported movie file")
        selected = max(candidates, key=lambda item: (item.size_bytes, -item.id))
        return await self.select_file(task_id, selected.id)

    async def episode_files(self, task_id: str) -> list[EpisodeFileBindingResponse]:
        await self._task(task_id)
        if self._episodes is None:
            return []
        bindings = await self._episodes.list_task_bindings(task_id)
        return [
            EpisodeFileBindingResponse(
                id=binding.id,
                episode_id=episode.id,
                media_id=episode.media_id,
                season_number=episode.season_number,
                episode_number=episode.episode_number,
                catalog_episode_id=episode.catalog_episode_id,
                file_variant_id=variant.id,
                file_id=variant.file_id,
                variant_label=variant.variant_label,
                confidence=binding.confidence,
                confirmation=binding.confirmation,
                segment_index=binding.segment_index,
            )
            for binding, episode, variant in bindings
        ]

    async def configure_prefetch(
        self,
        task_id: str,
        file_ids: list[int],
    ) -> TorrentStatus:
        task = await self._task(task_id)
        if task.selected_file_id is None:
            raise TorrentFileError("Select a video file before prefetching episodes")
        if len(file_ids) != len(set(file_ids)):
            raise TorrentFileError("Episode prefetch selection contains duplicates")

        files = await self._client.files(task.torrent_hash)
        requested_ids = set(file_ids)
        for file_id in requested_ids:
            if file_id < 0 or file_id >= len(files):
                raise TorrentFileError("A prefetched torrent file does not exist")
            if not self._to_file(file_id, files[file_id]).is_video:
                raise TorrentFileError("Only supported video files can be prefetched")

        enabled_ids = sorted(requested_ids | {task.selected_file_id})
        enabled_files = [self._to_file(file_id, files[file_id]) for file_id in enabled_ids]
        should_start = any(file.progress < 1 for file in enabled_files)
        start_required = await self._ensure_start_allowed(task) if should_start else False

        await self._client.set_file_priority(
            task.torrent_hash,
            list(range(len(files))),
            0,
        )
        await self._client.set_file_priority(task.torrent_hash, enabled_ids, 1)
        if start_required:
            await self._client.start(task.torrent_hash)
        return await self.status(task_id)

    async def start(self, task_id: str) -> TorrentStatus:
        task = await self._task(task_id)
        if task.selected_file_id is None:
            raise TorrentFileError("Select a video file before starting the download")
        if await self._ensure_start_allowed(task):
            await self._client.start(task.torrent_hash)
        return await self.status(task_id)

    async def _ensure_start_allowed(self, task: TorrentTask) -> bool:
        await self._ensure_free_space()
        torrents = await self._client.list()
        current = next(
            (item for item in torrents if str(item.get("hash", "")).lower() == task.torrent_hash),
            None,
        )
        if current is not None and self._is_active(current):
            return False
        active = [item for item in torrents if self._is_active(item)]
        if len(active) >= self._settings.max_active_torrents:
            raise TorrentLimitError("The active torrent limit has been reached")
        return True

    async def stop(self, task_id: str) -> TorrentStatus:
        task = await self._task(task_id)
        await self._client.stop(task.torrent_hash)
        return await self.status(task_id)

    async def _task(self, task_id: str) -> TorrentTask:
        task = await self._repository.get(task_id)
        if task is None:
            raise TorrentNotFoundError("Torrent task not found")
        return task

    async def _wait_for_torrent(self, known_hash: str, tag: str) -> dict[str, Any]:
        for _ in range(20):
            items = await self._client.list(torrent_hash=known_hash) if known_hash else []
            if not items:
                items = await self._client.list(tag=tag)
            if items:
                return items[0]
            await asyncio.sleep(0.25)
        raise TorrentUnavailableError("qBittorrent did not register the torrent in time")

    async def _ensure_free_space(self) -> None:
        try:
            root = Path(self._settings.torrent_storage_root).resolve(strict=True)
            save_path = Path(self._settings.torrent_save_path).resolve(strict=False)
            if not save_path.is_relative_to(root):
                raise TorrentStorageError(
                    "The torrent save path is outside the configured KADR storage root"
                )
            usage = await asyncio.to_thread(shutil.disk_usage, root)
        except OSError as exc:
            raise TorrentStorageError("KADR download storage is unavailable") from exc
        required_bytes = int(self._settings.min_free_space_gb * 1024**3)
        if usage.free < required_bytes:
            raise TorrentStorageError("Not enough free space to safely start another download")

    @staticmethod
    def _is_active(item: dict[str, Any]) -> bool:
        progress = min(max(float(item.get("progress") or 0), 0), 1)
        if progress >= 1:
            return False
        return str(item.get("state") or "unknown") not in STOPPED_STATES

    @staticmethod
    def _to_file(index: int, item: dict[str, Any]) -> TorrentFile:
        name = str(item.get("name") or f"file-{index}")
        raw_duration = item.get("duration_seconds") or item.get("duration")
        duration_seconds = int(raw_duration) if raw_duration else None
        return TorrentFile(
            id=index,
            name=name,
            size_bytes=max(int(item.get("size") or 0), 0),
            progress=min(max(float(item.get("progress") or 0), 0), 1),
            priority=max(int(item.get("priority") or 0), 0),
            is_video=PurePosixPath(name).suffix.lower() in VIDEO_EXTENSIONS,
            duration_seconds=(
                duration_seconds if duration_seconds is not None and duration_seconds > 0 else None
            ),
        )

    @staticmethod
    def _safe_relative_path(value: str) -> bool:
        normalized = value.replace("\\", "/")
        path = PurePosixPath(normalized)
        return (
            bool(value)
            and not path.is_absolute()
            and ".." not in path.parts
            and not (len(normalized) >= 3 and normalized[1:3] == ":/")
            and not any(ord(character) < 32 for character in value)
        )

    @staticmethod
    def _to_status(task: TorrentTask, item: dict[str, Any]) -> TorrentStatus:
        eta = int(item.get("eta") or 0)
        state = str(item.get("state") or task.state)
        available = state != "unavailable"
        return TorrentStatus(
            id=task.id,
            media_id=task.media_id,
            media_kind=task.media_kind,  # type: ignore[arg-type]
            name=str(item.get("name") or task.release_title),
            state=state,
            progress=min(max(float(item.get("progress") or 0), 0), 1),
            downloaded_bytes=max(int(item.get("downloaded") or 0), 0),
            total_size_bytes=max(int(item.get("size") or 0), 0),
            download_speed_bytes=max(int(item.get("dlspeed") or 0), 0),
            upload_speed_bytes=max(int(item.get("upspeed") or 0), 0),
            peers=max(int(item.get("num_leechs") or 0), 0),
            seeds=max(int(item.get("num_seeds") or 0), 0),
            eta_seconds=None if eta <= 0 or eta >= 8_640_000 else eta,
            selected_file_id=task.selected_file_id,
            selected_file_path=task.selected_file_path,
            can_start=(
                available
                and task.selected_file_id is not None
                and state in STOPPED_STATES
            ),
            can_stop=available and state not in STOPPED_STATES,
        )
