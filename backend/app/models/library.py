from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LibraryItem(Base):
    __tablename__ = "library_items"
    __table_args__ = (
        UniqueConstraint("media_kind", "media_id", name="uq_library_media"),
        Index("ix_library_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("torrent_tasks.id", ondelete="RESTRICT"), unique=True
    )
    media_id: Mapped[int] = mapped_column(Integer)
    media_kind: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(512))
    original_title: Mapped[str] = mapped_column(String(512), default="")
    poster_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    backdrop_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_path: Mapped[str] = mapped_column(String(1024), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("media_kind", "media_id", name="uq_favorite_media"),
        Index("ix_favorites_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    media_id: Mapped[int] = mapped_column(Integer)
    media_kind: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(512))
    original_title: Mapped[str] = mapped_column(String(512), default="")
    poster_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    backdrop_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )


class WatchHistory(Base):
    __tablename__ = "watch_history"
    __table_args__ = (
        UniqueConstraint("media_kind", "media_id", name="uq_history_media"),
        Index("ix_history_updated_at", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    media_id: Mapped[int] = mapped_column(Integer)
    media_kind: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(512))
    poster_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    position_seconds: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
