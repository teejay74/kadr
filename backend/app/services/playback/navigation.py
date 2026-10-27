from app.repositories.episodes import EpisodeRepository
from app.schemas.media import EpisodeSummary
from app.schemas.playback import (
    NextEpisodeRequest,
    NextEpisodeResolution,
    PlaybackResolveRequest,
)
from app.services.metadata.catalog import CatalogService
from app.services.playback.resolver import PlaybackResolver
from app.services.torrents.exceptions import (
    TorrentFileError,
    TorrentLimitError,
    TorrentNotConfiguredError,
    TorrentNotFoundError,
    TorrentStorageError,
    TorrentUnavailableError,
)
from app.services.torrents.manager import TorrentManager


class EpisodeNavigationService:
    """Resolve catalog episode order and keep prefetch bounded to one file."""

    def __init__(
        self,
        catalog: CatalogService,
        resolver: PlaybackResolver,
        episodes: EpisodeRepository,
        torrents: TorrentManager,
    ) -> None:
        self._catalog = catalog
        self._resolver = resolver
        self._episodes = episodes
        self._torrents = torrents

    async def resolve_next(
        self,
        request: NextEpisodeRequest,
    ) -> NextEpisodeResolution:
        episode = await self._next_episode(request)
        if episode is None:
            return NextEpisodeResolution(
                status="end",
                message="Это последний доступный эпизод сериала.",
            )

        combined = await self._uses_current_file(request, episode)
        if combined:
            return NextEpisodeResolution(
                status="unavailable",
                episode=episode,
                combined_file=True,
                message=(
                    "Следующий эпизод находится в том же объединённом файле. "
                    "Без временных границ KADR не может точно перейти к его началу."
                ),
            )

        playback = await self._resolver.resolve(
            PlaybackResolveRequest(
                media_kind="series",
                media_id=request.media_id,
                season_number=episode.season_number,
                episode_number=episode.number,
                catalog_episode_id=episode.id,
                profile_key=request.profile_key,
                preferred_task_id=request.current_task_id,
            )
        )
        return NextEpisodeResolution(
            status=playback.status,
            episode=episode,
            playback=playback,
            message=playback.message,
        )

    async def prefetch_next(
        self,
        request: NextEpisodeRequest,
    ) -> NextEpisodeResolution:
        episode = await self._next_episode(request)
        if episode is None:
            return NextEpisodeResolution(status="end")
        if not request.current_task_id:
            return NextEpisodeResolution(
                status="source_required",
                episode=episode,
                message="Предбуферизация доступна для активной torrent-раздачи.",
            )

        logical = await self._episodes.find(
            request.media_id,
            episode.season_number,
            episode.number,
        )
        if logical is None:
            return NextEpisodeResolution(status="source_required", episode=episode)
        variants = await self._episodes.list_episode_variants(logical.id)
        variant = next(
            (
                item
                for item, task in variants
                if task.id == request.current_task_id
            ),
            None,
        )
        if variant is None:
            return NextEpisodeResolution(status="source_required", episode=episode)
        if request.current_file_id == variant.file_id:
            return NextEpisodeResolution(
                status="unavailable",
                episode=episode,
                combined_file=True,
                message="Следующий эпизод уже находится в текущем объединённом файле.",
            )
        try:
            await self._torrents.configure_prefetch(
                request.current_task_id,
                [variant.file_id],
            )
        except (
            TorrentFileError,
            TorrentLimitError,
            TorrentNotConfiguredError,
            TorrentNotFoundError,
            TorrentStorageError,
            TorrentUnavailableError,
        ):
            return NextEpisodeResolution(
                status="unavailable",
                episode=episode,
                message="Не удалось подготовить следующий эпизод заранее.",
            )
        return NextEpisodeResolution(
            status="buffering",
            episode=episode,
            prefetched=True,
        )

    async def _next_episode(
        self,
        request: NextEpisodeRequest,
    ) -> EpisodeSummary | None:
        details = await self._catalog.details("series", request.media_id)
        season_numbers = sorted(
            season.number for season in details.seasons if season.number > 0
        )
        if request.season_number not in season_numbers:
            season_numbers.append(request.season_number)
            season_numbers.sort()

        start = season_numbers.index(request.season_number)
        season = await self._catalog.season(request.media_id, request.season_number)
        episodes = sorted(season.episodes, key=lambda item: item.number)
        for position, item in enumerate(episodes):
            identity_matches = (
                item.id == request.catalog_episode_id
                if request.catalog_episode_id is not None
                else item.number == request.episode_number
            )
            if identity_matches:
                if position + 1 < len(episodes):
                    return episodes[position + 1]
                return await self._first_in_later_season(
                    request.media_id, season_numbers[start + 1 :]
                )
        return None

    async def _first_in_later_season(
        self,
        media_id: int,
        season_numbers: list[int],
    ) -> EpisodeSummary | None:
        for season_number in season_numbers:
            season = await self._catalog.season(media_id, season_number)
            if season.episodes:
                return min(season.episodes, key=lambda item: item.number)
        return None

    async def _uses_current_file(
        self,
        request: NextEpisodeRequest,
        episode: EpisodeSummary,
    ) -> bool:
        if request.current_task_id is None or request.current_file_id is None:
            return False
        logical = await self._episodes.find(
            request.media_id,
            episode.season_number,
            episode.number,
        )
        if logical is None:
            return False
        variants = await self._episodes.list_episode_variants(logical.id)
        return any(
            task.id == request.current_task_id
            and variant.file_id == request.current_file_id
            for variant, task in variants
        )
