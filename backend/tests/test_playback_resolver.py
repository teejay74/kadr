from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_playback_resolver
from app.main import app
from app.models.library import LibraryItem, WatchHistory
from app.models.torrent_task import TorrentTask
from app.repositories.episodes import EpisodeRepository
from app.repositories.library import LibraryRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.playback import PlaybackResolution, PlaybackResolveRequest
from app.schemas.torrents import StreamReadiness, TorrentStatus
from app.services.playback.resolver import PlaybackResolver
from app.services.torrents.exceptions import TorrentUnavailableError


class FakeLibraryManager:
    def __init__(self, available: bool = True) -> None:
        self.available = available

    async def playback_available(self, _: LibraryItem) -> bool:
        return self.available


class FakeTorrentManager:
    def __init__(self, *, unavailable: bool = False) -> None:
        self.unavailable = unavailable
        self.calls: list[tuple[object, ...]] = []
        self.preferred_calls: list[str] = []

    async def select_preferred_movie_file(self, task_id: str) -> TorrentStatus:
        self.preferred_calls.append(task_id)
        if self.unavailable:
            raise TorrentUnavailableError("offline")
        return TorrentStatus(
            id=task_id,
            media_id=42,
            media_kind="movie",
            name="Movie",
            state="stoppedDL",
            progress=0,
            downloaded_bytes=0,
            total_size_bytes=1000,
            download_speed_bytes=0,
            upload_speed_bytes=0,
            peers=0,
            seeds=1,
            eta_seconds=None,
            selected_file_id=4,
            selected_file_path="Movie.mkv",
            can_start=True,
            can_stop=False,
        )

    async def select_file(self, *args: object) -> TorrentStatus:
        self.calls.append(args)
        if self.unavailable:
            raise TorrentUnavailableError("offline")
        task_id, file_id = str(args[0]), int(args[1])
        return TorrentStatus(
            id=task_id,
            media_id=42,
            media_kind="series",
            name="Series",
            state="downloading",
            progress=0.5,
            downloaded_bytes=500,
            total_size_bytes=1000,
            download_speed_bytes=100,
            upload_speed_bytes=0,
            peers=1,
            seeds=2,
            eta_seconds=5,
            selected_file_id=file_id,
            selected_file_path="Series.S01E02.mkv",
            can_start=False,
            can_stop=True,
        )


class FakeStreamingManager:
    def __init__(self, ready: bool = True) -> None:
        self.ready = ready
        self.calls: list[str] = []

    async def readiness(self, task_id: str) -> StreamReadiness:
        self.calls.append(task_id)
        return StreamReadiness(
            ready=self.ready,
            buffer_progress=1 if self.ready else 0.4,
        )


def resolver(
    session: AsyncSession,
    *,
    library_available: bool = True,
    torrent_unavailable: bool = False,
    ready: bool = True,
) -> tuple[PlaybackResolver, FakeTorrentManager, FakeStreamingManager]:
    torrents = FakeTorrentManager(unavailable=torrent_unavailable)
    streaming = FakeStreamingManager(ready=ready)
    service = PlaybackResolver(
        EpisodeRepository(session),
        LibraryRepository(session),
        TorrentTaskRepository(session),
        FakeLibraryManager(library_available),  # type: ignore[arg-type]
        torrents,  # type: ignore[arg-type]
        streaming,  # type: ignore[arg-type]
    )
    return service, torrents, streaming


@pytest.mark.asyncio
async def test_resolver_prefers_saved_library_and_returns_resume(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    del tmp_path
    task = TorrentTask(
        id="00000000-0000-0000-0000-000000000201",
        media_id=42,
        media_kind="movie",
        torrent_hash="movie-hash",
        source_id="a" * 24,
        release_title="Movie",
        selected_file_id=3,
        selected_file_path="movie.mkv",
        storage_path="/downloads/cache",
        state="stoppedUP",
    )
    await TorrentTaskRepository(session).create(task)
    library = LibraryItem(
        id="00000000-0000-0000-0000-000000000202",
        task_id=task.id,
        file_id=3,
        media_id=42,
        media_kind="movie",
        title="Movie",
        original_title="",
        file_path="/library/movie.mkv",
        size_bytes=100,
    )
    history = WatchHistory(
        id="00000000-0000-0000-0000-000000000203",
        media_id=42,
        media_kind="movie",
        profile_key="default",
        title="Movie",
        position_seconds=125,
        duration_seconds=600,
        completed=False,
    )
    session.add_all([library, history])
    await session.commit()
    service, torrents, streaming = resolver(session)

    result = await service.resolve(
        PlaybackResolveRequest(media_kind="movie", media_id=42)
    )

    assert result.status == "ready"
    assert result.source == "library"
    assert result.stream_url == f"/api/v1/library/{library.id}/stream"
    assert result.resume_position_seconds == 125
    assert torrents.calls == []
    assert streaming.calls == []


@pytest.mark.asyncio
async def test_resolver_reuses_bound_episode_file_and_reports_buffering(
    session: AsyncSession,
) -> None:
    task = TorrentTask(
        id="00000000-0000-0000-0000-000000000204",
        media_id=42,
        media_kind="series",
        torrent_hash="series-hash",
        source_id="b" * 24,
        release_title="Series S01",
        selected_file_id=0,
        selected_file_path="Series.S01E01.mkv",
        storage_path="/downloads/cache",
        state="stoppedDL",
    )
    await TorrentTaskRepository(session).create(task)
    episodes = EpisodeRepository(session)
    await episodes.bind_file(task, 1, "Series.S01E02.mkv", 1, 2, 1002, "1080p")
    service, torrents, streaming = resolver(session, ready=False)

    result = await service.resolve(
        PlaybackResolveRequest(
            media_kind="series",
            media_id=42,
            season_number=1,
            episode_number=2,
            catalog_episode_id=1002,
        )
    )

    assert result.status == "buffering"
    assert result.source == "torrent"
    assert result.task_id == task.id
    assert result.file_id == 1
    assert result.buffer_progress == 0.4
    assert torrents.calls[0][0:5] == (task.id, 1, 1, 2, 1002)
    assert streaming.calls == [task.id]


@pytest.mark.asyncio
async def test_resolver_requires_source_without_saved_media_or_binding(
    session: AsyncSession,
) -> None:
    service, _, _ = resolver(session)

    result = await service.resolve(
        PlaybackResolveRequest(
            media_kind="series",
            media_id=42,
            season_number=1,
            episode_number=1,
        )
    )

    assert result.status == "source_required"
    assert result.source is None
    assert result.stream_url is None


@pytest.mark.asyncio
async def test_resolver_selects_movie_file_on_backend_for_a_new_source(
    session: AsyncSession,
) -> None:
    task = TorrentTask(
        id="00000000-0000-0000-0000-000000000206",
        media_id=42,
        media_kind="movie",
        torrent_hash="new-movie-hash",
        source_id="d" * 24,
        release_title="Movie 1080p",
        storage_path="/downloads/cache",
        state="stoppedDL",
    )
    await TorrentTaskRepository(session).create(task)
    service, torrents, streaming = resolver(session)

    result = await service.resolve(
        PlaybackResolveRequest(media_kind="movie", media_id=42)
    )

    assert result.status == "ready"
    assert result.file_id == 4
    assert torrents.preferred_calls == [task.id]
    assert torrents.calls[0][0:2] == (task.id, 4)
    assert streaming.calls == [task.id]


@pytest.mark.asyncio
async def test_resolver_reports_unavailable_bound_source(
    session: AsyncSession,
) -> None:
    task = TorrentTask(
        id="00000000-0000-0000-0000-000000000205",
        media_id=42,
        media_kind="series",
        torrent_hash="offline-hash",
        source_id="c" * 24,
        release_title="Series S01",
        storage_path="/downloads/cache",
        state="error",
    )
    await TorrentTaskRepository(session).create(task)
    await EpisodeRepository(session).bind_file(
        task,
        0,
        "Series.S01E01.mkv",
        1,
        1,
    )
    service, _, _ = resolver(session, torrent_unavailable=True)

    result = await service.resolve(
        PlaybackResolveRequest(
            media_kind="series",
            media_id=42,
            season_number=1,
            episode_number=1,
        )
    )

    assert result.status == "unavailable"
    assert result.message is not None


@pytest.mark.asyncio
async def test_playback_resolve_api_uses_unified_contract(client: AsyncClient) -> None:
    class FakeResolver:
        async def resolve(self, body: PlaybackResolveRequest) -> PlaybackResolution:
            assert body.media_id == 42
            return PlaybackResolution(status="source_required")

    app.dependency_overrides[get_playback_resolver] = lambda: FakeResolver()

    response = await client.post(
        "/api/v1/playback/resolve",
        json={"media_kind": "movie", "media_id": 42},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "source_required"
