import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.episodes import EpisodeFileBinding, MediaEpisode, TorrentFileVariant
from app.models.torrent_task import TorrentTask


class EpisodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, episode_id: str | None) -> MediaEpisode | None:
        if episode_id is None:
            return None
        return await self._session.get(MediaEpisode, episode_id)

    async def find(
        self,
        media_id: int,
        season_number: int,
        episode_number: int,
    ) -> MediaEpisode | None:
        result = await self._session.execute(
            select(MediaEpisode).where(
                MediaEpisode.media_id == media_id,
                MediaEpisode.season_number == season_number,
                MediaEpisode.episode_number == episode_number,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        media_id: int,
        season_number: int,
        episode_number: int,
        catalog_episode_id: int | None = None,
    ) -> MediaEpisode:
        episode = await self.find(media_id, season_number, episode_number)
        if episode is None:
            episode = MediaEpisode(
                id=str(uuid.uuid4()),
                media_id=media_id,
                season_number=season_number,
                episode_number=episode_number,
                catalog_episode_id=catalog_episode_id,
            )
            self._session.add(episode)
            await self._session.flush()
        elif catalog_episode_id is not None and episode.catalog_episode_id is None:
            episode.catalog_episode_id = catalog_episode_id
            await self._session.flush()
        return episode

    async def bind_file(
        self,
        task: TorrentTask,
        file_id: int,
        file_path: str,
        season_number: int,
        episode_number: int,
        catalog_episode_id: int | None = None,
        variant_label: str | None = None,
    ) -> EpisodeFileBinding:
        episode = await self.get_or_create(
            task.media_id,
            season_number,
            episode_number,
            catalog_episode_id,
        )
        result = await self._session.execute(
            select(TorrentFileVariant).where(
                TorrentFileVariant.task_id == task.id,
                TorrentFileVariant.file_id == file_id,
            )
        )
        variant = result.scalar_one_or_none()
        if variant is None:
            variant = TorrentFileVariant(
                id=str(uuid.uuid4()),
                task_id=task.id,
                file_id=file_id,
                file_path=file_path,
                variant_label=variant_label,
            )
            self._session.add(variant)
            await self._session.flush()
        else:
            variant.file_path = file_path
            if variant_label is not None:
                variant.variant_label = variant_label

        result = await self._session.execute(
            select(EpisodeFileBinding).where(
                EpisodeFileBinding.episode_id == episode.id,
                EpisodeFileBinding.file_variant_id == variant.id,
            )
        )
        binding = result.scalar_one_or_none()
        if binding is None:
            binding = EpisodeFileBinding(
                id=str(uuid.uuid4()),
                episode_id=episode.id,
                file_variant_id=variant.id,
            )
            self._session.add(binding)
        await self._session.commit()
        return binding

    async def list_task_bindings(
        self,
        task_id: str,
    ) -> list[tuple[EpisodeFileBinding, MediaEpisode, TorrentFileVariant]]:
        result = await self._session.execute(
            select(EpisodeFileBinding, MediaEpisode, TorrentFileVariant)
            .join(MediaEpisode, MediaEpisode.id == EpisodeFileBinding.episode_id)
            .join(
                TorrentFileVariant,
                TorrentFileVariant.id == EpisodeFileBinding.file_variant_id,
            )
            .where(TorrentFileVariant.task_id == task_id)
            .order_by(
                MediaEpisode.season_number,
                MediaEpisode.episode_number,
                TorrentFileVariant.file_id,
            )
        )
        return list(result.tuples())

    async def list_episode_variants(
        self,
        episode_id: str,
    ) -> list[tuple[TorrentFileVariant, TorrentTask]]:
        result = await self._session.execute(
            select(TorrentFileVariant, TorrentTask)
            .join(
                EpisodeFileBinding,
                EpisodeFileBinding.file_variant_id == TorrentFileVariant.id,
            )
            .join(TorrentTask, TorrentTask.id == TorrentFileVariant.task_id)
            .where(EpisodeFileBinding.episode_id == episode_id)
            .order_by(TorrentTask.created_at.desc(), TorrentFileVariant.file_id)
        )
        return list(result.tuples())
