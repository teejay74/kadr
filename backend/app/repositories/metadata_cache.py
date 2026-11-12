from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy import text
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

    async def find_catalogue_item(
        self, media_id: int, *, title_key: str, date_key: str
    ) -> dict[str, Any] | None:
        result = await self._session.execute(
            text("""
                SELECT item.value
                FROM metadata_cache AS cache
                CROSS JOIN json_each(cache.payload, '$.results') AS item
                WHERE CASE WHEN item.type = 'object' THEN
                    json_extract(item.value, '$.id') = :media_id
                    AND json_type(item.value, :title_path) = 'text'
                    AND json_type(item.value, :date_path) IS NOT NULL
                ELSE 0 END
                ORDER BY cache.updated_at DESC
                LIMIT 1
            """),
            {"media_id": media_id, "title_path": f"$.{title_key}", "date_path": f"$.{date_key}"},
        )
        payload = result.scalar_one_or_none()
        return json.loads(payload) if payload is not None else None

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
