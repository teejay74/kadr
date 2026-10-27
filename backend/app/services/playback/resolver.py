from app.models.episodes import MediaEpisode
from app.models.torrent_task import TorrentTask
from app.repositories.episodes import EpisodeRepository
from app.repositories.library import LibraryRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.playback import PlaybackResolution, PlaybackResolveRequest
from app.services.library.manager import LibraryManager
from app.services.streaming.exceptions import StreamNotReadyError
from app.services.streaming.manager import StreamingManager
from app.services.torrents.exceptions import (
    TorrentFileError,
    TorrentLimitError,
    TorrentNotConfiguredError,
    TorrentNotFoundError,
    TorrentStorageError,
    TorrentUnavailableError,
)
from app.services.torrents.manager import TorrentManager


class PlaybackResolver:
    def __init__(
        self,
        episodes: EpisodeRepository,
        library: LibraryRepository,
        tasks: TorrentTaskRepository,
        library_manager: LibraryManager,
        torrent_manager: TorrentManager,
        streaming_manager: StreamingManager,
    ) -> None:
        self._episodes = episodes
        self._library = library
        self._tasks = tasks
        self._library_manager = library_manager
        self._torrent_manager = torrent_manager
        self._streaming_manager = streaming_manager

    async def resolve(self, request: PlaybackResolveRequest) -> PlaybackResolution:
        episode = await self._episode(request)
        resume_position = await self._resume_position(request, episode)
        stale_source = False

        library_item = await self._library.get_library_by_media(
            request.media_id,
            request.media_kind,
            episode.id if episode else None,
        )
        if library_item is not None:
            if await self._library_manager.playback_available(library_item):
                return PlaybackResolution(
                    status="ready",
                    source="library",
                    stream_url=f"/api/v1/library/{library_item.id}/stream",
                    task_id=library_item.task_id,
                    file_id=library_item.file_id,
                    library_item_id=library_item.id,
                    resume_position_seconds=resume_position,
                    buffer_progress=1,
                    download_progress=1,
                    download_state="saved",
                )
            stale_source = True

        if request.season_number is not None:
            if episode is None:
                return self._missing(resume_position, stale_source)
            candidates = await self._episodes.list_episode_variants(episode.id)
            if not candidates:
                return self._missing(resume_position, stale_source)
            for variant, task in candidates:
                result = await self._torrent(
                    request,
                    task,
                    variant.file_id,
                    resume_position,
                )
                if result is not None:
                    return result
            return self._unavailable(resume_position)

        task = await self._tasks.get_latest_by_media(
            request.media_id,
            request.media_kind,
        )
        if task is None or task.selected_file_id is None:
            return self._missing(resume_position, stale_source)
        result = await self._torrent(
            request,
            task,
            task.selected_file_id,
            resume_position,
        )
        return result or self._unavailable(resume_position)

    async def _torrent(
        self,
        request: PlaybackResolveRequest,
        task: TorrentTask,
        file_id: int,
        resume_position: int,
    ) -> PlaybackResolution | None:
        try:
            status = await self._torrent_manager.select_file(
                task.id,
                file_id,
                request.season_number,
                request.episode_number,
                request.catalog_episode_id,
            )
            readiness = await self._streaming_manager.readiness(task.id)
        except (
            StreamNotReadyError,
            TorrentFileError,
            TorrentLimitError,
            TorrentNotConfiguredError,
            TorrentNotFoundError,
            TorrentStorageError,
            TorrentUnavailableError,
        ):
            return None
        return PlaybackResolution(
            status="ready" if readiness.ready else "buffering",
            source="torrent",
            stream_url=f"/api/v1/torrents/{task.id}/stream",
            task_id=task.id,
            file_id=file_id,
            resume_position_seconds=resume_position,
            buffer_progress=readiness.buffer_progress,
            download_progress=status.progress,
            download_state=status.state,
            download_speed_bytes=status.download_speed_bytes,
        )

    async def _episode(
        self,
        request: PlaybackResolveRequest,
    ) -> MediaEpisode | None:
        if request.season_number is None or request.episode_number is None:
            return None
        return await self._episodes.find(
            request.media_id,
            request.season_number,
            request.episode_number,
        )

    async def _resume_position(
        self,
        request: PlaybackResolveRequest,
        episode: MediaEpisode | None,
    ) -> int:
        history = await self._library.get_history(
            request.media_id,
            request.media_kind,
            request.profile_key,
            episode.id if episode else None,
        )
        if history is None or history.completed:
            return 0
        return history.position_seconds

    @staticmethod
    def _missing(resume_position: int, stale_source: bool) -> PlaybackResolution:
        if stale_source:
            return PlaybackResolver._unavailable(resume_position)
        return PlaybackResolution(
            status="source_required",
            resume_position_seconds=resume_position,
            message="Выберите источник для начала просмотра.",
        )

    @staticmethod
    def _unavailable(resume_position: int) -> PlaybackResolution:
        return PlaybackResolution(
            status="unavailable",
            resume_position_seconds=resume_position,
            message="Сохранённый источник сейчас недоступен. Выберите другой.",
        )
