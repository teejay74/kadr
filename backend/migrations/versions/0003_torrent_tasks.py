"""Create torrent task records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_torrent_tasks"
down_revision: str | None = "0002_metadata_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "torrent_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column("media_kind", sa.String(length=10), nullable=False),
        sa.Column("torrent_hash", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=24), nullable=False),
        sa.Column("release_title", sa.String(length=512), nullable=False),
        sa.Column("selected_file_id", sa.Integer(), nullable=True),
        sa.Column("selected_file_path", sa.String(length=1024), nullable=True),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("torrent_hash"),
    )
    op.create_index("ix_torrent_tasks_media", "torrent_tasks", ["media_kind", "media_id"])
    op.create_index("ix_torrent_tasks_state", "torrent_tasks", ["state"])


def downgrade() -> None:
    op.drop_index("ix_torrent_tasks_state", table_name="torrent_tasks")
    op.drop_index("ix_torrent_tasks_media", table_name="torrent_tasks")
    op.drop_table("torrent_tasks")
