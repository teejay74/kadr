"""Persist the watched portions of an episode."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_episode_played_ranges"
down_revision: str | None = "0007_playback_track_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("watch_history", sa.Column("played_ranges_ms", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("watch_history", "played_ranges_ms")
