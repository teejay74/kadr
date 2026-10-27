from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.library import Favorite, LibraryItem, WatchHistory


class LibraryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_library(self) -> list[LibraryItem]:
        result = await self._session.execute(
            select(LibraryItem).order_by(LibraryItem.created_at.desc())
        )
        return list(result.scalars())

    async def get_library(self, item_id: str) -> LibraryItem | None:
        return await self._session.get(LibraryItem, item_id)

    async def get_library_by_task_file(
        self,
        task_id: str,
        file_id: int,
    ) -> LibraryItem | None:
        result = await self._session.execute(
            select(LibraryItem).where(
                LibraryItem.task_id == task_id,
                or_(LibraryItem.file_id == file_id, LibraryItem.file_id.is_(None)),
            )
        )
        return result.scalar_one_or_none()

    async def has_library_for_task(self, task_id: str) -> bool:
        result = await self._session.execute(
            select(LibraryItem.id).where(LibraryItem.task_id == task_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_library_by_media(
        self,
        media_id: int,
        media_kind: str,
        episode_id: str | None = None,
    ) -> LibraryItem | None:
        result = await self._session.execute(
            select(LibraryItem).where(
                LibraryItem.media_id == media_id,
                LibraryItem.media_kind == media_kind,
                LibraryItem.episode_id == episode_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_library(self, item: LibraryItem) -> LibraryItem:
        self._session.add(item)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            existing = await self.get_library_by_media(
                item.media_id,
                item.media_kind,
                item.episode_id,
            )
            if existing is None:
                raise
            return existing
        await self._session.refresh(item)
        return item

    async def delete_library(self, item: LibraryItem) -> None:
        await self._session.delete(item)
        await self._session.commit()

    async def list_favorites(self) -> list[Favorite]:
        result = await self._session.execute(select(Favorite).order_by(Favorite.created_at.desc()))
        return list(result.scalars())

    async def get_favorite(self, media_id: int, media_kind: str) -> Favorite | None:
        result = await self._session.execute(
            select(Favorite).where(Favorite.media_id == media_id, Favorite.media_kind == media_kind)
        )
        return result.scalar_one_or_none()

    async def add_favorite(self, item: Favorite) -> Favorite:
        self._session.add(item)
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def delete_favorite(self, media_id: int, media_kind: str) -> bool:
        result = await self._session.execute(
            delete(Favorite).where(Favorite.media_id == media_id, Favorite.media_kind == media_kind)
        )
        await self._session.commit()
        return bool(result.rowcount)

    async def list_history(self, profile_key: str = "default") -> list[WatchHistory]:
        result = await self._session.execute(
            select(WatchHistory)
            .where(WatchHistory.profile_key == profile_key)
            .order_by(WatchHistory.updated_at.desc())
        )
        return list(result.scalars())

    async def get_history(
        self,
        media_id: int,
        media_kind: str,
        profile_key: str = "default",
        episode_id: str | None = None,
    ) -> WatchHistory | None:
        result = await self._session.execute(
            select(WatchHistory).where(
                WatchHistory.media_id == media_id,
                WatchHistory.media_kind == media_kind,
                WatchHistory.profile_key == profile_key,
                WatchHistory.episode_id == episode_id,
            )
        )
        return result.scalar_one_or_none()

    async def save_history(self, item: WatchHistory) -> WatchHistory:
        self._session.add(item)
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def library_totals(self) -> tuple[int, int]:
        result = await self._session.execute(
            select(func.count(LibraryItem.id), func.coalesce(func.sum(LibraryItem.size_bytes), 0))
        )
        count, size = result.one()
        return int(count), int(size)
