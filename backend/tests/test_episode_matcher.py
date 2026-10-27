from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_episode_matcher
from app.main import app
from app.models.torrent_task import TorrentTask
from app.repositories.episodes import EpisodeRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.episode_matcher import (
    EpisodeMatchConfirmationRequest,
    EpisodeMatchIdentity,
    EpisodeMatchSelection,
)
from app.schemas.media import EpisodeSummary, SeasonDetails
from app.schemas.torrents import TorrentFile
from app.services.episodes.matcher import EpisodeMatcher
from app.services.torrents.exceptions import TorrentFileError


class FakeCatalog:
    def __init__(self) -> None:
        self.episodes = {
            1: [
                EpisodeSummary(
                    id=1001,
                    season_number=1,
                    number=1,
                    name="Pilot One",
                    overview="",
                    runtime_minutes=45,
                ),
                EpisodeSummary(
                    id=1002,
                    season_number=1,
                    number=2,
                    name="Pilot Two",
                    overview="",
                    runtime_minutes=46,
                ),
                EpisodeSummary(
                    id=1003,
                    season_number=1,
                    number=3,
                    name="The Return",
                    overview="",
                    runtime_minutes=44,
                ),
            ]
        }

    async def season(self, media_id: int, season_number: int) -> SeasonDetails:
        assert media_id == 42
        return SeasonDetails(
            id=season_number,
            series_id=media_id,
            number=season_number,
            name=f"Season {season_number}",
            overview="",
            episodes=self.episodes.get(season_number, []),
        )

    async def details(self, kind: str, media_id: int) -> object:
        raise AssertionError("details are unnecessary when paths contain a season")


class FakeTorrents:
    def __init__(self, files: list[TorrentFile]) -> None:
        self._files = files

    async def files(self, task_id: str) -> list[TorrentFile]:
        return self._files


async def make_matcher(
    session: AsyncSession,
    files: list[TorrentFile],
) -> tuple[EpisodeMatcher, TorrentTask]:
    task = TorrentTask(
        id="00000000-0000-0000-0000-000000000301",
        media_id=42,
        media_kind="series",
        torrent_hash="matcher-hash",
        source_id="a" * 24,
        release_title="Example Season 1",
        storage_path="/downloads/cache",
        state="stoppedDL",
    )
    tasks = TorrentTaskRepository(session)
    await tasks.create(task)
    matcher = EpisodeMatcher(
        FakeCatalog(),  # type: ignore[arg-type]
        FakeTorrents(files),  # type: ignore[arg-type]
        tasks,
        EpisodeRepository(session),
    )
    return matcher, task


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("Show.S01E02.mkv", [(1, 2)]),
        ("Show 1x02.mp4", [(1, 2)]),
        ("Show Season 1 Episode 2.mkv", [(1, 2)]),
        ("Шоу/Сезон 1/Серия 2.mkv", [(1, 2)]),
        ("Show.S01E01E02.mkv", [(1, 1), (1, 2)]),
        ("Show.S01E01-E03.mkv", [(1, 1), (1, 2), (1, 3)]),
        ("Show 1x01-03.mkv", [(1, 1), (1, 2), (1, 3)]),
        ("Сезон 1 Серии 1-3.mkv", [(1, 1), (1, 2), (1, 3)]),
    ],
)
def test_parser_supports_standard_russian_ranges_and_combined_episodes(
    path: str,
    expected: list[tuple[int, int]],
) -> None:
    parsed = EpisodeMatcher.parse_path(path)

    assert [(item.season, item.episode) for item in parsed.episodes] == expected
    assert parsed.unsafe is False


@pytest.mark.parametrize(
    "path",
    [
        "../Season 1/Show.S01E01.mkv",
        "/downloads/Show.S01E01.mkv",
        "C:\\downloads\\Show.S01E01.mkv",
        "Season 1/Show.S01E01\x00.mkv",
    ],
)
def test_parser_rejects_unsafe_torrent_paths(path: str) -> None:
    assert EpisodeMatcher.parse_path(path).unsafe is True


@pytest.mark.asyncio
async def test_exact_matches_are_persisted_and_reused_after_restart(
    session: AsyncSession,
) -> None:
    files = [
        TorrentFile(
            id=4,
            name="Show/Season 1/Show.S01E01E02.mkv",
            size_bytes=100,
            progress=0,
            priority=0,
            is_video=True,
            duration_seconds=5400,
        )
    ]
    matcher, task = await make_matcher(
        session,
        files,
    )

    first = await matcher.analyze(task.id)
    restarted = EpisodeMatcher(
        FakeCatalog(),  # type: ignore[arg-type]
        FakeTorrents(files),  # type: ignore[arg-type]
        TorrentTaskRepository(session),
        EpisodeRepository(session),
    )
    second = await restarted.analyze(task.id)

    assert first.files[0].confidence == "exact"
    assert first.files[0].confirmed is True
    assert first.files[0].confirmation == "automatic"
    assert [(item.season_number, item.episode_number) for item in first.files[0].episodes] == [
        (1, 1),
        (1, 2),
    ]
    assert second.files[0].confirmed is True
    assert len(await EpisodeRepository(session).list_task_bindings(task.id)) == 2


@pytest.mark.asyncio
async def test_duration_is_auxiliary_and_does_not_trigger_automatic_binding(
    session: AsyncSession,
) -> None:
    matcher, task = await make_matcher(
        session,
        [
            TorrentFile(
                id=0,
                name="Show.S01E02.mkv",
                size_bytes=100,
                progress=0,
                priority=0,
                is_video=True,
                duration_seconds=9000,
            )
        ],
    )

    report = await matcher.analyze(task.id)

    assert report.files[0].confidence == "probable"
    assert report.files[0].confirmed is False
    assert await EpisodeRepository(session).list_task_bindings(task.id) == []


@pytest.mark.asyncio
async def test_conflicting_and_title_only_files_require_confirmation(
    session: AsyncSession,
) -> None:
    matcher, task = await make_matcher(
        session,
        [
            TorrentFile(
                id=0,
                name="Disc A/Show.S01E01.mkv",
                size_bytes=100,
                progress=0,
                priority=0,
                is_video=True,
            ),
            TorrentFile(
                id=1,
                name="Disc B/Show.S01E01.mkv",
                size_bytes=100,
                progress=0,
                priority=0,
                is_video=True,
            ),
            TorrentFile(
                id=2,
                name="Season 1/Pilot.mkv",
                size_bytes=100,
                progress=0,
                priority=0,
                is_video=True,
            ),
        ],
    )

    report = await matcher.analyze(task.id)

    assert report.requires_confirmation is True
    assert report.files[0].confidence == "ambiguous"
    assert report.files[1].confidence == "ambiguous"
    assert report.files[2].confidence == "ambiguous"
    assert await EpisodeRepository(session).list_task_bindings(task.id) == []


@pytest.mark.asyncio
async def test_unique_title_match_is_probable_and_never_automatic(
    session: AsyncSession,
) -> None:
    matcher, task = await make_matcher(
        session,
        [
            TorrentFile(
                id=0,
                name="Season 1/The Return.mkv",
                size_bytes=100,
                progress=0,
                priority=0,
                is_video=True,
            )
        ],
    )

    report = await matcher.analyze(task.id)

    assert report.files[0].confidence == "probable"
    assert report.files[0].episodes[0].episode_number == 3
    assert report.files[0].confirmed is False
    assert await EpisodeRepository(session).list_task_bindings(task.id) == []


@pytest.mark.asyncio
async def test_manual_confirmation_persists_multiple_episodes_for_one_file(
    session: AsyncSession,
) -> None:
    matcher, task = await make_matcher(
        session,
        [
            TorrentFile(
                id=0,
                name="Season 1/Combined Feature.mkv",
                size_bytes=100,
                progress=0,
                priority=0,
                is_video=True,
            )
        ],
    )

    report = await matcher.confirm(
        task.id,
        EpisodeMatchConfirmationRequest(
            mappings=[
                EpisodeMatchSelection(
                    file_id=0,
                    episodes=[
                        EpisodeMatchIdentity(season_number=1, episode_number=1),
                        EpisodeMatchIdentity(season_number=1, episode_number=2),
                    ],
                )
            ]
        ),
    )

    assert report.files[0].confirmed is True
    assert report.files[0].confirmation == "manual"
    assert len(report.files[0].episodes) == 2


@pytest.mark.asyncio
async def test_unsafe_path_is_never_automatically_or_manually_bound(
    session: AsyncSession,
) -> None:
    matcher, task = await make_matcher(
        session,
        [
            TorrentFile(
                id=0,
                name="../Season 1/Show.S01E01.mkv",
                size_bytes=100,
                progress=0,
                priority=0,
                is_video=True,
            )
        ],
    )

    report = await matcher.analyze(task.id)

    assert report.files[0].unsafe is True
    assert report.files[0].confidence == "ambiguous"
    with pytest.raises(TorrentFileError, match="unsafe torrent path"):
        await matcher.confirm(
            task.id,
            EpisodeMatchConfirmationRequest(
                mappings=[
                    EpisodeMatchSelection(
                        file_id=0,
                        episodes=[EpisodeMatchIdentity(season_number=1, episode_number=1)],
                    )
                ]
            ),
        )


def test_episode_matcher_migration_preserves_existing_bindings(tmp_path: Path) -> None:
    database = tmp_path / "matcher-migration.db"
    project_root = Path(__file__).resolve().parents[1]
    environment = {
        **os.environ,
        "KADR_DATABASE_URL": f"sqlite+aiosqlite:///{database}",
    }
    subprocess.run(
        ["alembic", "upgrade", "0005_episode_persistence"],
        cwd=project_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        """
        INSERT INTO torrent_tasks (
            id, media_id, media_kind, torrent_hash, source_id, release_title,
            storage_path, state
        ) VALUES ('task', 42, 'series', 'hash', ?, 'Show S01', '/cache', 'stoppedDL')
        """,
        ("a" * 24,),
    )
    connection.execute(
        "INSERT INTO media_episodes (id, media_id, season_number, episode_number) "
        "VALUES ('episode', 42, 1, 1)"
    )
    connection.execute(
        "INSERT INTO torrent_file_variants (id, task_id, file_id, file_path) "
        "VALUES ('variant', 'task', 0, 'Show.S01E01.mkv')"
    )
    connection.execute(
        "INSERT INTO episode_file_bindings (id, episode_id, file_variant_id) "
        "VALUES ('binding', 'episode', 'variant')"
    )
    connection.commit()
    connection.close()

    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=project_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    connection = sqlite3.connect(database)
    row = connection.execute(
        "SELECT confidence, confirmation, segment_index "
        "FROM episode_file_bindings WHERE id = 'binding'"
    ).fetchone()
    assert row == ("exact", "manual", None)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE episode_file_bindings SET confidence = 'invented' WHERE id = 'binding'"
        )
    connection.close()


@pytest.mark.asyncio
async def test_episode_matcher_api_exposes_analysis_and_confirmation(
    client: AsyncClient,
) -> None:
    class FakeMatcher:
        async def analyze(self, task_id: str) -> dict[str, object]:
            return {
                "task_id": task_id,
                "metadata_available": True,
                "files": [],
                "requires_confirmation": False,
            }

        async def confirm(
            self,
            task_id: str,
            request: EpisodeMatchConfirmationRequest,
        ) -> dict[str, object]:
            assert request.mappings[0].file_id == 7
            assert len(request.mappings[0].episodes) == 2
            return await self.analyze(task_id)

    app.dependency_overrides[get_episode_matcher] = lambda: FakeMatcher()

    analyzed = await client.post("/api/v1/torrents/task-id/episode-matches/analyze")
    confirmed = await client.put(
        "/api/v1/torrents/task-id/episode-matches",
        json={
            "mappings": [
                {
                    "file_id": 7,
                    "episodes": [
                        {"season_number": 1, "episode_number": 1},
                        {"season_number": 1, "episode_number": 2},
                    ],
                }
            ]
        },
    )

    assert analyzed.status_code == 200
    assert confirmed.status_code == 200
    assert confirmed.json()["task_id"] == "task-id"
