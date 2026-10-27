from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MediaEpisode(Base):
    __tablename__ = "media_episodes"
    __table_args__ = (
        CheckConstraint("season_number >= 0", name="ck_media_episode_season"),
        CheckConstraint("episode_number >= 1", name="ck_media_episode_number"),
        UniqueConstraint(
            "media_id",
            "season_number",
            "episode_number",
            name="uq_media_episode_identity",
        ),
        Index("ix_media_episodes_series_season", "media_id", "season_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    media_id: Mapped[int] = mapped_column(Integer)
    season_number: Mapped[int] = mapped_column(Integer)
    episode_number: Mapped[int] = mapped_column(Integer)
    catalog_episode_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )


class TorrentFileVariant(Base):
    __tablename__ = "torrent_file_variants"
    __table_args__ = (
        UniqueConstraint("task_id", "file_id", name="uq_torrent_file_variant"),
        Index("ix_torrent_file_variants_task", "task_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("torrent_tasks.id", ondelete="CASCADE")
    )
    file_id: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(String(1024))
    variant_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )


class EpisodeFileBinding(Base):
    __tablename__ = "episode_file_bindings"
    __table_args__ = (
        CheckConstraint(
            "confidence IN ('exact', 'probable', 'ambiguous')",
            name="ck_episode_file_binding_confidence",
        ),
        CheckConstraint(
            "confirmation IN ('automatic', 'manual')",
            name="ck_episode_file_binding_confirmation",
        ),
        CheckConstraint(
            "segment_index IS NULL OR segment_index >= 1",
            name="ck_episode_file_binding_segment",
        ),
        UniqueConstraint("episode_id", "file_variant_id", name="uq_episode_file_binding"),
        Index("ix_episode_file_bindings_episode", "episode_id"),
        Index("ix_episode_file_bindings_file", "file_variant_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    episode_id: Mapped[str] = mapped_column(
        ForeignKey("media_episodes.id", ondelete="CASCADE")
    )
    file_variant_id: Mapped[str] = mapped_column(
        ForeignKey("torrent_file_variants.id", ondelete="CASCADE")
    )
    confidence: Mapped[str] = mapped_column(String(16), default="exact")
    confirmation: Mapped[str] = mapped_column(String(16), default="manual")
    segment_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )
