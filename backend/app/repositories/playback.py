from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.playback import PlaybackTrackPreference


class PlaybackTrackPreferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, profile_key: str) -> PlaybackTrackPreference | None:
        result = await self._session.execute(
            select(PlaybackTrackPreference).where(
                PlaybackTrackPreference.profile_key == profile_key
            )
        )
        return result.scalar_one_or_none()

    async def save(
        self,
        preference: PlaybackTrackPreference,
    ) -> PlaybackTrackPreference:
        profile_key = preference.profile_key
        values = {
            column: getattr(preference, column)
            for column in (
                "audio_preference_key",
                "audio_language",
                "audio_title",
                "audio_codec",
                "subtitle_preference_key",
                "subtitle_language",
                "subtitle_title",
                "subtitle_codec",
                "subtitles_enabled",
            )
        }
        self._session.add(preference)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            existing = await self.get(profile_key)
            if existing is None:
                raise
            for column, value in values.items():
                setattr(existing, column, value)
            preference = existing
            await self._session.commit()
        await self._session.refresh(preference)
        return preference
