from pathlib import Path, PurePosixPath

from app.core.config import Settings
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.playback import PlaybackPreparation
from app.services.playback.exceptions import (
    PlaybackArtifactNotReadyError,
    PlaybackPreparationError,
)
from app.services.playback.manager import CompatibilityManager
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
    ) -> None:
        self._manager = manager
        self._client = client
        self._repository = repository
        self._settings = settings

    async def prepare(self, task_id: str) -> PlaybackPreparation:
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
        if not source.is_file():
            raise PlaybackPreparationError("The selected video file is unavailable")
        return await self._manager.start(task_id, task.selected_file_id, source)

    async def status(self, task_id: str) -> PlaybackPreparation:
        task = await self._repository.get(task_id)
        if task is None or task.selected_file_id is None:
            return PlaybackPreparation(state="idle", progress=0)
        return self._manager.status(task_id, task.selected_file_id)

    async def open(
        self,
        task_id: str,
        range_header: str | None,
        registry: StreamRegistry,
    ) -> PreparedStream:
        task = await self._repository.get(task_id)
        if task is None or task.selected_file_id is None:
            raise PlaybackArtifactNotReadyError(
                "Select a video file before compatible playback"
            )
        return await self._manager.open(
            task_id,
            task.selected_file_id,
            range_header,
            registry,
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
