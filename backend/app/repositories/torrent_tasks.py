from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.torrent_task import TorrentTask


class TorrentTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, task: TorrentTask) -> TorrentTask:
        self._session.add(task)
        await self._session.commit()
        await self._session.refresh(task)
        return task

    async def get(self, task_id: str) -> TorrentTask | None:
        return await self._session.get(TorrentTask, task_id)

    async def get_by_hash(self, torrent_hash: str) -> TorrentTask | None:
        result = await self._session.execute(
            select(TorrentTask).where(TorrentTask.torrent_hash == torrent_hash)
        )
        return result.scalar_one_or_none()

    async def select_file(self, task: TorrentTask, file_id: int, file_path: str) -> None:
        task.selected_file_id = file_id
        task.selected_file_path = file_path
        await self._session.commit()

    async def set_state(self, task: TorrentTask, state: str) -> None:
        task.state = state
        await self._session.commit()
