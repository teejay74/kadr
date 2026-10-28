"""Add profile-scoped semantic playback track preferences."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_playback_track_preferences"
down_revision: str | None = "0006_episode_matcher"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "playback_track_preferences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_key", sa.String(length=64), nullable=False),
        sa.Column("audio_preference_key", sa.String(length=64), nullable=True),
        sa.Column("audio_language", sa.String(length=35), nullable=True),
        sa.Column("audio_title", sa.String(length=200), nullable=True),
        sa.Column("audio_codec", sa.String(length=64), nullable=True),
        sa.Column("subtitle_preference_key", sa.String(length=64), nullable=True),
        sa.Column("subtitle_language", sa.String(length=35), nullable=True),
        sa.Column("subtitle_title", sa.String(length=200), nullable=True),
        sa.Column("subtitle_codec", sa.String(length=64), nullable=True),
        sa.Column(
            "subtitles_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_playback_track_preferences_profile",
        "playback_track_preferences",
        ["profile_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_playback_track_preferences_profile",
        table_name="playback_track_preferences",
    )
    op.drop_table("playback_track_preferences")
