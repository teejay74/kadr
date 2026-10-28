import asyncio
from pathlib import Path, PurePosixPath

from app.core.config import Settings
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.playback import PlaybackMode, PlaybackPreparation
from app.services.playback.exceptions import (
    PlaybackArtifactNotReadyError,
    PlaybackPreparationError,
    PlaybackTrackPreferenceError,
)
from app.services.playback.manager import CompatibilityManager
from app.services.playback.tracks import PlaybackTrackProbe
from app.services.streaming.manager import PreparedStream
from app.services.streaming.registry import StreamRegistry
from app.services.torrents.qbittorrent import QBittorrentClient


class PlaybackPreparationService:
    def __init__(
        self,
        manager: CompatibilityManager,
        client: QBittorrentClient,
        repository: TorrentTaskRepository,
        settings: Settings,
        track_probe: PlaybackTrackProbe,
    ) -> None:
        self._manager = manager
        self._client = client
        self._repository = repository
        self._settings = settings
        self._track_probe = track_probe

    async def prepare(
        self,
        task_id: str,
        mode: PlaybackMode = "compatible",
        track_id: str | None = None,
    ) -> PlaybackPreparation:
        task = await self._repository.get(task_id)
        if (
            task is None
            or task.selected_file_id is None
            or task.selected_file_path is None
        ):
            raise PlaybackPreparationError("Select a video file before preparation")
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
            raise PlaybackPreparationError(
                "The selected video must finish downloading before FFmpeg preparation"
            )
        source = self._safe_source(task.storage_path, task.selected_file_path)
        if not await asyncio.to_thread(source.is_file):
            raise PlaybackPreparationError("The selected video file is unavailable")
        audio_stream_index: int | None = None
        if mode == "audio_track":
            if track_id is None:
                raise PlaybackTrackPreferenceError("Select an audio track")
            tracks = await self._track_probe.probe(source)
            track = next(
                (item for item in tracks.audio_tracks if item.id == track_id),
                None,
            )
            if track is None:
                raise PlaybackTrackPreferenceError(
                    "The selected audio track does not belong to this file"
                )
            audio_stream_index = track.stream_index
        return await self._manager.start(
            task_id,
            task.selected_file_id,
            source,
            mode,
            audio_stream_index,
            track_id,
        )

    async def status(
        self,
        task_id: str,
        mode: PlaybackMode = "compatible",
        track_id: str | None = None,
    ) -> PlaybackPreparation:
        task = await self._repository.get(task_id)
        if task is None or task.selected_file_id is None:
            return PlaybackPreparation(mode=mode, state="idle", progress=0)
        return self._manager.status(task_id, task.selected_file_id, mode, track_id)

    async def cancel(
        self,
        task_id: str,
        mode: PlaybackMode = "compatible",
        track_id: str | None = None,
    ) -> PlaybackPreparation:
        task = await self._repository.get(task_id)
        if task is None or task.selected_file_id is None:
            return PlaybackPreparation(mode=mode, state="idle", progress=0)
        return await self._manager.cancel(
            task_id,
            task.selected_file_id,
            mode,
            track_id,
        )

    async def open(
        self,
        task_id: str,
        mode: PlaybackMode,
        range_header: str | None,
        registry: StreamRegistry,
        track_id: str | None = None,
    ) -> PreparedStream:
        task = await self._repository.get(task_id)
        if task is None or task.selected_file_id is None:
            raise PlaybackArtifactNotReadyError(
                "Select a video file before compatible playback"
            )
        return await self._manager.open(
            task_id,
            task.selected_file_id,
            mode,
            range_header,
            registry,
            track_id,
        )

    def _safe_source(self, storage_path: str, relative_path: str) -> Path:
        relative = PurePosixPath(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise PlaybackPreparationError("The selected video path is unsafe")
        try:
            root = Path(self._settings.torrent_storage_root).resolve(strict=True)
            storage = Path(storage_path).resolve(strict=False)
            source = (storage / Path(*relative.parts)).resolve(strict=False)
        except OSError as exc:
            raise PlaybackPreparationError(
                "KADR download storage is unavailable"
            ) from exc
        if not storage.is_relative_to(root) or not source.is_relative_to(root):
            raise PlaybackPreparationError("The selected video is outside KADR storage")
        return source
