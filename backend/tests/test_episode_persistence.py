from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.torrent_task import TorrentTask
from app.repositories.episodes import EpisodeRepository
from app.repositories.library import LibraryRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.library import HistoryUpdateRequest
from app.services.library.manager import LibraryManager
from app.services.streaming.registry import StreamRegistry


@pytest.mark.asyncio
async def test_one_torrent_task_binds_multiple_episodes_and_variants(
    session: AsyncSession,
) -> None:
    task = TorrentTask(
        id="00000000-0000-0000-0000-000000000101",
        media_id=42,
        media_kind="series",
        torrent_hash="episode-bindings",
        source_id="a" * 24,
        release_title="Example S01",
        selected_file_id=0,
        selected_file_path="Example.S01E01.mkv",
        storage_path="/downloads/cache",
        state="stoppedDL",
    )
    await TorrentTaskRepository(session).create(task)
    episodes = EpisodeRepository(session)

    await episodes.bind_file(task, 0, "Example.S01E01.mkv", 1, 1, 1001, "1080p")
    await episodes.bind_file(task, 1, "Example.S01E02.mkv", 1, 2, 1002, "1080p")
    await episodes.bind_file(task, 2, "Example.S01E01.2160p.mkv", 1, 1, 1001, "2160p")
    await episodes.bind_file(task, 0, "Example.S01E01.mkv", 1, 1, 1001, "1080p")

    bindings = await episodes.list_task_bindings(task.id)
    assert [(episode.episode_number, variant.file_id) for _, episode, variant in bindings] == [
        (1, 0),
        (1, 2),
        (2, 1),
    ]
    assert task.selected_file_id == 0


@pytest.mark.asyncio
async def test_watch_history_is_independent_by_episode_and_profile(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    manager = LibraryManager(
        LibraryRepository(session),
        TorrentTaskRepository(session),
        object(),  # type: ignore[arg-type]
        StreamRegistry(2),
        Settings(library_root=str(tmp_path)),
        EpisodeRepository(session),
    )

    first = await manager.history(
        42,
        HistoryUpdateRequest(
            media_kind="series",
            title="Example",
            season_number=1,
            episode_number=1,
            catalog_episode_id=1001,
            position_seconds=120,
            duration_seconds=3600,
        ),
    )
    second = await manager.history(
        42,
        HistoryUpdateRequest(
            media_kind="series",
            title="Example",
            season_number=1,
            episode_number=2,
            catalog_episode_id=1002,
            position_seconds=240,
            duration_seconds=3600,
        ),
    )
    other_profile = await manager.history(
        42,
        HistoryUpdateRequest(
            media_kind="series",
            profile_key="guest",
            title="Example",
            season_number=1,
            episode_number=1,
            position_seconds=30,
            duration_seconds=3600,
        ),
    )

    assert first.id != second.id
    assert first.episode is not None and first.episode.episode_number == 1
    assert second.episode is not None and second.episode.episode_number == 2
    assert other_profile.id != first.id
    assert (await manager.get_history(42, "series", "default", 1, 1)).position_seconds == 120  # type: ignore[union-attr]
    assert (await manager.get_history(42, "series", "guest", 1, 1)).position_seconds == 30  # type: ignore[union-attr]


def test_sqlite_migration_preserves_legacy_rows_and_nullable_uniqueness(
    tmp_path: Path,
) -> None:
    database = tmp_path / "migration.db"
    project_root = Path(__file__).resolve().parents[1]
    environment = {
        **os.environ,
        "KADR_DATABASE_URL": f"sqlite+aiosqlite:///{database}",
    }
    subprocess.run(
        ["alembic", "upgrade", "0004_library"],
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
            selected_file_id, selected_file_path, storage_path, state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("legacy-task", 42, "movie", "legacy-hash", "a" * 24, "Legacy", 7,
         "legacy.mkv", "/downloads/cache", "stoppedUP"),
    )
    connection.execute(
        """
        INSERT INTO library_items (
            id, task_id, media_id, media_kind, title, original_title,
            file_path, size_bytes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("legacy-library", "legacy-task", 42, "movie", "Legacy", "",
         "/library/legacy.mkv", 10),
    )
    connection.execute(
        """
        INSERT INTO watch_history (
            id, media_id, media_kind, title, position_seconds, duration_seconds, completed
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("legacy-history", 42, "movie", "Legacy", 10, 100, 0),
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
    connection.execute("PRAGMA foreign_keys=ON")
    assert connection.execute(
        "SELECT task_id, file_id, episode_id FROM library_items WHERE id = 'legacy-library'"
    ).fetchone() == ("legacy-task", 7, None)
    assert connection.execute(
        "SELECT profile_key, episode_id FROM watch_history WHERE id = 'legacy-history'"
    ).fetchone() == ("default", None)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO watch_history (
                id, media_id, media_kind, profile_key, title,
                position_seconds, duration_seconds, completed
            ) VALUES ('duplicate-root', 42, 'movie', 'default', 'Duplicate', 0, 0, 0)
            """
        )
    connection.rollback()
    connection.execute(
        """
        INSERT INTO watch_history (
            id, media_id, media_kind, profile_key, title,
            position_seconds, duration_seconds, completed
        ) VALUES ('guest-root', 42, 'movie', 'guest', 'Guest', 0, 0, 0)
        """
    )
    connection.execute(
        """
        INSERT INTO media_episodes (id, media_id, season_number, episode_number)
        VALUES ('episode-1', 99, 1, 1), ('episode-2', 99, 1, 2)
        """
    )
    for item_id, episode_id in (("history-e1", "episode-1"), ("history-e2", "episode-2")):
        connection.execute(
            """
            INSERT INTO watch_history (
                id, media_id, media_kind, profile_key, episode_id, title,
                position_seconds, duration_seconds, completed
            ) VALUES (?, 99, 'series', 'default', ?, 'Series', 0, 0, 0)
            """,
            (item_id, episode_id),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO watch_history (
                id, media_id, media_kind, profile_key, episode_id, title,
                position_seconds, duration_seconds, completed
            ) VALUES ('duplicate-e1', 99, 'series', 'default', 'episode-1', 'Series', 0, 0, 0)
            """
        )
    connection.close()
