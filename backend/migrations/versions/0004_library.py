"""Create library, favorites, and watch history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_library"
down_revision: str | None = "0003_torrent_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "library_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column("media_kind", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("original_title", sa.String(length=512), nullable=False),
        sa.Column("poster_url", sa.String(length=1024), nullable=True),
        sa.Column("backdrop_url", sa.String(length=1024), nullable=True),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["torrent_tasks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_path"),
        sa.UniqueConstraint("task_id"),
        sa.UniqueConstraint("media_kind", "media_id", name="uq_library_media"),
    )
    op.create_index("ix_library_created_at", "library_items", ["created_at"])
    op.create_table(
        "favorites",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column("media_kind", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("original_title", sa.String(length=512), nullable=False),
        sa.Column("poster_url", sa.String(length=1024), nullable=True),
        sa.Column("backdrop_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_kind", "media_id", name="uq_favorite_media"),
    )
    op.create_index("ix_favorites_created_at", "favorites", ["created_at"])
    op.create_table(
        "watch_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column("media_kind", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("poster_url", sa.String(length=1024), nullable=True),
        sa.Column("position_seconds", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_kind", "media_id", name="uq_history_media"),
    )
    op.create_index("ix_history_updated_at", "watch_history", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_history_updated_at", table_name="watch_history")
    op.drop_table("watch_history")
    op.drop_index("ix_favorites_created_at", table_name="favorites")
    op.drop_table("favorites")
    op.drop_index("ix_library_created_at", table_name="library_items")
    op.drop_table("library_items")
