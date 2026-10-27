from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.torrent_task import TorrentTask
from app.repositories.episodes import EpisodeRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.media import EpisodeSummary, SeasonDetails
from app.schemas.playback import (
    NextEpisodeRequest,
    PlaybackResolution,
    PlaybackResolveRequest,
)
from app.services.playback.navigation import EpisodeNavigationService


def episode(season: int, number: int, catalog_id: int) -> EpisodeSummary:
    return EpisodeSummary(
        id=catalog_id,
        season_number=season,
        number=number,
        name=f"S{season}E{number}",
        overview="",
    )


class FakeCatalog:
    def __init__(self) -> None:
        self.seasons = {
            1: [episode(1, 1, 101), episode(1, 3, 103)],
            2: [episode(2, 2, 202)],
        }
        self.calls: list[int] = []

    async def details(self, kind: str, media_id: int) -> SimpleNamespace:
        assert kind == "series"
        assert media_id == 42
        return SimpleNamespace(
            seasons=[SimpleNamespace(number=1), SimpleNamespace(number=2)]
        )

    async def season(self, media_id: int, number: int) -> SeasonDetails:
        assert media_id == 42
        self.calls.append(number)
        return SeasonDetails(
            id=number,
            series_id=media_id,
            number=number,
            name=f"Season {number}",
            overview="",
            episodes=self.seasons[number],
        )


class FakeResolver:
    def __init__(self) -> None:
        self.requests: list[PlaybackResolveRequest] = []

    async def resolve(self, request: PlaybackResolveRequest) -> PlaybackResolution:
        self.requests.append(request)
        return PlaybackResolution(
            status="ready",
            source="torrent",
            task_id=request.preferred_task_id,
            file_id=7,
        )


class FakeTorrents:
    def __init__(self) -> None:
        self.prefetch_calls: list[tuple[str, list[int]]] = []

    async def configure_prefetch(self, task_id: str, file_ids: list[int]) -> None:
        self.prefetch_calls.append((task_id, file_ids))


def service(
    session: AsyncSession,
) -> tuple[EpisodeNavigationService, FakeCatalog, FakeResolver, FakeTorrents]:
    catalog = FakeCatalog()
    resolver = FakeResolver()
    torrents = FakeTorrents()
    navigation = EpisodeNavigationService(
        catalog,  # type: ignore[arg-type]
        resolver,  # type: ignore[arg-type]
        EpisodeRepository(session),
        torrents,  # type: ignore[arg-type]
    )
    return navigation, catalog, resolver, torrents


@pytest.mark.asyncio
async def test_next_episode_uses_catalog_order_instead_of_incrementing(
    session: AsyncSession,
) -> None:
    navigation, _, resolver, _ = service(session)

    result = await navigation.resolve_next(
        NextEpisodeRequest(
            media_id=42,
            season_number=1,
            episode_number=1,
            catalog_episode_id=101,
            current_task_id="task-1",
        )
    )

    assert result.status == "ready"
    assert result.episode is not None
    assert result.episode.number == 3
    assert resolver.requests[0].episode_number == 3
    assert resolver.requests[0].preferred_task_id == "task-1"


@pytest.mark.asyncio
async def test_next_episode_crosses_season_using_catalog_metadata(
    session: AsyncSession,
) -> None:
    navigation, catalog, _, _ = service(session)

    result = await navigation.resolve_next(
        NextEpisodeRequest(
            media_id=42,
            season_number=1,
            episode_number=3,
            catalog_episode_id=103,
        )
    )

    assert result.episode is not None
    assert (result.episode.season_number, result.episode.number) == (2, 2)
    assert catalog.calls == [1, 2]


@pytest.mark.asyncio
async def test_unknown_current_catalog_identity_does_not_skip_to_next_season(
    session: AsyncSession,
) -> None:
    navigation, _, resolver, _ = service(session)

    result = await navigation.resolve_next(
        NextEpisodeRequest(
            media_id=42,
            season_number=1,
            episode_number=3,
            catalog_episode_id=999,
        )
    )

    assert result.status == "end"
    assert resolver.requests == []


@pytest.mark.asyncio
async def test_prefetch_enables_only_the_next_bound_file(
    session: AsyncSession,
) -> None:
    task = TorrentTask(
        id="00000000-0000-0000-0000-000000000301",
        media_id=42,
        media_kind="series",
        torrent_hash="navigation-hash",
        source_id="n" * 24,
        release_title="Series",
        selected_file_id=1,
        selected_file_path="S01E01.mkv",
        storage_path="/downloads/cache",
        state="downloading",
    )
    await TorrentTaskRepository(session).create(task)
    await EpisodeRepository(session).bind_file(task, 7, "S01E03.mkv", 1, 3, 103)
    navigation, _, _, torrents = service(session)

    result = await navigation.prefetch_next(
        NextEpisodeRequest(
            media_id=42,
            season_number=1,
            episode_number=1,
            current_task_id=task.id,
            current_file_id=1,
        )
    )

    assert result.prefetched is True
    assert torrents.prefetch_calls == [(task.id, [7])]


@pytest.mark.asyncio
async def test_combined_file_does_not_claim_an_exact_next_episode_seek(
    session: AsyncSession,
) -> None:
    task = TorrentTask(
        id="00000000-0000-0000-0000-000000000302",
        media_id=42,
        media_kind="series",
        torrent_hash="combined-hash",
        source_id="c" * 24,
        release_title="Series combined",
        selected_file_id=5,
        selected_file_path="S01E01-E03.mkv",
        storage_path="/downloads/cache",
        state="downloading",
    )
    await TorrentTaskRepository(session).create(task)
    episodes = EpisodeRepository(session)
    await episodes.bind_file(task, 5, "S01E01-E03.mkv", 1, 3, 103)
    navigation, _, resolver, _ = service(session)

    result = await navigation.resolve_next(
        NextEpisodeRequest(
            media_id=42,
            season_number=1,
            episode_number=1,
            current_task_id=task.id,
            current_file_id=5,
        )
    )

    assert result.status == "unavailable"
    assert result.combined_file is True
    assert resolver.requests == []
