"""Create metadata response cache."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_metadata_cache"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metadata_cache",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index("ix_metadata_cache_expires_at", "metadata_cache", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_metadata_cache_expires_at", table_name="metadata_cache")
    op.drop_table("metadata_cache")
