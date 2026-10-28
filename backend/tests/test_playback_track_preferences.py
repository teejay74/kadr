import os
import sqlite3
import subprocess
from pathlib import Path

import pytest


def test_preference_migration_preserves_existing_sqlite_data_and_profiles(
    tmp_path: Path,
) -> None:
    database = tmp_path / "track-preferences.db"
    project_root = Path(__file__).resolve().parents[1]
    environment = {
        **os.environ,
        "KADR_DATABASE_URL": f"sqlite+aiosqlite:///{database}",
    }
    subprocess.run(
        ["alembic", "upgrade", "0006_episode_matcher"],
        cwd=project_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO application_state (key, value) VALUES ('legacy', 'preserved')"
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
    assert connection.execute(
        "SELECT value FROM application_state WHERE key = 'legacy'"
    ).fetchone() == ("preserved",)
    connection.execute(
        """
        INSERT INTO playback_track_preferences (
            id, profile_key, audio_language, subtitles_enabled
        ) VALUES ('preference-1', 'default', 'ru', 0)
        """
    )
    connection.execute(
        """
        INSERT INTO playback_track_preferences (
            id, profile_key, audio_language, subtitles_enabled
        ) VALUES ('preference-2', 'guest', 'en', 1)
        """
    )
    connection.commit()
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO playback_track_preferences (
                id, profile_key, subtitles_enabled
            ) VALUES ('preference-3', 'default', 0)
            """
        )
    connection.rollback()
    assert connection.execute(
        "SELECT COUNT(*) FROM playback_track_preferences"
    ).fetchone() == (2,)
    connection.close()
