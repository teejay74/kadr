from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metadata_cache import MetadataCache


class MetadataCacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str, *, allow_expired: bool = False) -> dict[str, Any] | None:
        entry = await self._session.get(MetadataCache, key)
        if entry is None or (not allow_expired and entry.expires_at <= int(time.time())):
            return None
        payload = json.loads(entry.payload)
        return payload if isinstance(payload, dict) else None

    async def set(self, key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        statement = insert(MetadataCache).values(
            key=key,
            payload=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            expires_at=int(time.time()) + ttl_seconds,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[MetadataCache.key],
            set_={
                "payload": statement.excluded.payload,
                "expires_at": statement.excluded.expires_at,
                "updated_at": statement.excluded.updated_at,
            },
        )
        await self._session.execute(statement)
        await self._session.commit()
