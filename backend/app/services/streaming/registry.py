import asyncio
from collections import Counter

from app.services.streaming.exceptions import StreamLimitError


class StreamLease:
    def __init__(self, registry: "StreamRegistry", task_id: str) -> None:
        self._registry = registry
        self._task_id = task_id
        self._released = False

    async def release(self) -> None:
        if self._released:
            return
        self._released = True
        await self._registry.release(self._task_id)


class StreamRegistry:
    def __init__(self, limit: int, requests_per_task: int = 8) -> None:
        self._limit = limit
        self._requests_per_task = requests_per_task
        self._tasks: Counter[str] = Counter()
        self._lock = asyncio.Lock()

    async def acquire(self, task_id: str) -> StreamLease:
        async with self._lock:
            is_new_task = self._tasks[task_id] == 0
            if is_new_task and len(self._tasks) >= self._limit:
                raise StreamLimitError("The active stream limit has been reached")
            if self._tasks[task_id] >= self._requests_per_task:
                raise StreamLimitError("The stream range-request limit has been reached")
            self._tasks[task_id] += 1
        return StreamLease(self, task_id)

    async def release(self, task_id: str) -> None:
        async with self._lock:
            if self._tasks[task_id] <= 0:
                return
            self._tasks[task_id] -= 1
            if self._tasks[task_id] == 0:
                del self._tasks[task_id]

    async def active_count(self) -> int:
        async with self._lock:
            return len(self._tasks)

    async def is_active(self, task_id: str) -> bool:
        async with self._lock:
            return self._tasks[task_id] > 0
