from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TorrentTask(Base):
    __tablename__ = "torrent_tasks"
    __table_args__ = (
        Index("ix_torrent_tasks_media", "media_kind", "media_id"),
        Index("ix_torrent_tasks_state", "state"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    media_id: Mapped[int] = mapped_column(Integer)
    media_kind: Mapped[str] = mapped_column(String(10))
    torrent_hash: Mapped[str] = mapped_column(String(64), unique=True)
    source_id: Mapped[str] = mapped_column(String(24))
    release_title: Mapped[str] = mapped_column(String(512))
    selected_file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(1024))
    state: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
