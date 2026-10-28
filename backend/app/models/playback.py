from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlaybackTrackPreference(Base):
    __tablename__ = "playback_track_preferences"
    __table_args__ = (
        Index(
            "uq_playback_track_preferences_profile",
            "profile_key",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_key: Mapped[str] = mapped_column(String(64), nullable=False)
    audio_preference_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audio_language: Mapped[str | None] = mapped_column(String(35), nullable=True)
    audio_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    audio_codec: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subtitle_preference_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subtitle_language: Mapped[str | None] = mapped_column(String(35), nullable=True)
    subtitle_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subtitle_codec: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subtitles_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
