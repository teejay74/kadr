"""Persist episode matcher confidence and confirmation provenance."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_episode_matcher"
down_revision: str | None = "0005_episode_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("episode_file_bindings") as batch:
        batch.add_column(
            sa.Column(
                "confidence",
                sa.String(length=16),
                nullable=False,
                server_default="exact",
            )
        )
        batch.add_column(
            sa.Column(
                "confirmation",
                sa.String(length=16),
                nullable=False,
                server_default="manual",
            )
        )
        batch.add_column(sa.Column("segment_index", sa.Integer(), nullable=True))
        batch.create_check_constraint(
            "ck_episode_file_binding_confidence",
            "confidence IN ('exact', 'probable', 'ambiguous')",
        )
        batch.create_check_constraint(
            "ck_episode_file_binding_confirmation",
            "confirmation IN ('automatic', 'manual')",
        )
        batch.create_check_constraint(
            "ck_episode_file_binding_segment",
            "segment_index IS NULL OR segment_index >= 1",
        )


def downgrade() -> None:
    with op.batch_alter_table("episode_file_bindings") as batch:
        batch.drop_constraint(
            "ck_episode_file_binding_segment",
            type_="check",
        )
        batch.drop_constraint(
            "ck_episode_file_binding_confirmation",
            type_="check",
        )
        batch.drop_constraint(
            "ck_episode_file_binding_confidence",
            type_="check",
        )
        batch.drop_column("segment_index")
        batch.drop_column("confirmation")
        batch.drop_column("confidence")
