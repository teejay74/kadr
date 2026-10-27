"""Add episode identity, file variants, and episode-aware persistence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_episode_persistence"
down_revision: str | None = "0004_library"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def upgrade() -> None:
    op.create_table(
        "media_episodes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column("season_number", sa.Integer(), nullable=False),
        sa.Column("episode_number", sa.Integer(), nullable=False),
        sa.Column("catalog_episode_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("season_number >= 0", name="ck_media_episode_season"),
        sa.CheckConstraint("episode_number >= 1", name="ck_media_episode_number"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "media_id",
            "season_number",
            "episode_number",
            name="uq_media_episode_identity",
        ),
    )
    op.create_index(
        "ix_media_episodes_series_season",
        "media_episodes",
        ["media_id", "season_number"],
    )
    op.create_table(
        "torrent_file_variants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("variant_label", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["torrent_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "file_id", name="uq_torrent_file_variant"),
    )
    op.create_index(
        "ix_torrent_file_variants_task", "torrent_file_variants", ["task_id"]
    )
    op.create_table(
        "episode_file_bindings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("episode_id", sa.String(length=36), nullable=False),
        sa.Column("file_variant_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["media_episodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["file_variant_id"], ["torrent_file_variants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", "file_variant_id", name="uq_episode_file_binding"),
    )
    op.create_index(
        "ix_episode_file_bindings_episode", "episode_file_bindings", ["episode_id"]
    )
    op.create_index(
        "ix_episode_file_bindings_file", "episode_file_bindings", ["file_variant_id"]
    )

    with op.batch_alter_table(
        "library_items",
        recreate="always",
        naming_convention=NAMING_CONVENTION,
    ) as batch:
        batch.add_column(sa.Column("episode_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("file_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_library_items_episode_id_media_episodes",
            "media_episodes",
            ["episode_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.drop_constraint("uq_library_media", type_="unique")
        batch.drop_constraint("uq_library_items_task_id", type_="unique")
    op.execute(
        "UPDATE library_items SET file_id = ("
        "SELECT selected_file_id FROM torrent_tasks "
        "WHERE torrent_tasks.id = library_items.task_id"
        ")"
    )
    op.create_index(
        "uq_library_media_root",
        "library_items",
        ["media_kind", "media_id"],
        unique=True,
        sqlite_where=sa.text("episode_id IS NULL"),
    )
    op.create_index(
        "uq_library_media_episode",
        "library_items",
        ["media_kind", "media_id", "episode_id"],
        unique=True,
        sqlite_where=sa.text("episode_id IS NOT NULL"),
    )
    op.create_index(
        "uq_library_task_file",
        "library_items",
        ["task_id", "file_id"],
        unique=True,
        sqlite_where=sa.text("file_id IS NOT NULL"),
    )

    with op.batch_alter_table(
        "watch_history",
        recreate="always",
        naming_convention=NAMING_CONVENTION,
    ) as batch:
        batch.add_column(
            sa.Column(
                "profile_key",
                sa.String(length=64),
                nullable=False,
                server_default="default",
            )
        )
        batch.add_column(sa.Column("episode_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_watch_history_episode_id_media_episodes",
            "media_episodes",
            ["episode_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.drop_constraint("uq_history_media", type_="unique")
    op.create_index(
        "uq_history_profile_media_root",
        "watch_history",
        ["profile_key", "media_kind", "media_id"],
        unique=True,
        sqlite_where=sa.text("episode_id IS NULL"),
    )
    op.create_index(
        "uq_history_profile_media_episode",
        "watch_history",
        ["profile_key", "media_kind", "media_id", "episode_id"],
        unique=True,
        sqlite_where=sa.text("episode_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_history_profile_media_episode", table_name="watch_history")
    op.drop_index("uq_history_profile_media_root", table_name="watch_history")
    with op.batch_alter_table(
        "watch_history",
        recreate="always",
        naming_convention=NAMING_CONVENTION,
    ) as batch:
        batch.drop_column("episode_id")
        batch.drop_column("profile_key")
        batch.create_unique_constraint("uq_history_media", ["media_kind", "media_id"])

    op.drop_index("uq_library_task_file", table_name="library_items")
    op.drop_index("uq_library_media_episode", table_name="library_items")
    op.drop_index("uq_library_media_root", table_name="library_items")
    with op.batch_alter_table(
        "library_items",
        recreate="always",
        naming_convention=NAMING_CONVENTION,
    ) as batch:
        batch.drop_column("file_id")
        batch.drop_column("episode_id")
        batch.create_unique_constraint("uq_library_media", ["media_kind", "media_id"])
        batch.create_unique_constraint("uq_library_items_task_id", ["task_id"])

    op.drop_index("ix_episode_file_bindings_file", table_name="episode_file_bindings")
    op.drop_index("ix_episode_file_bindings_episode", table_name="episode_file_bindings")
    op.drop_table("episode_file_bindings")
    op.drop_index("ix_torrent_file_variants_task", table_name="torrent_file_variants")
    op.drop_table("torrent_file_variants")
    op.drop_index("ix_media_episodes_series_season", table_name="media_episodes")
    op.drop_table("media_episodes")
