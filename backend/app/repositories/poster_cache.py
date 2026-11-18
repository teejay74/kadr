"""Persistent size-bounded image cache, separate from media and SQLite."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
import uuid
from pathlib import Path

from app.core.config import Settings

logger = logging.getLogger(__name__)


class PosterCacheRepository:
    def __init__(self, settings: Settings) -> None:
        self.root = Path(settings.poster_cache_root).resolve()
        self.ttl = settings.poster_cache_ttl_seconds
        self.limit = settings.poster_cache_max_bytes
        self.item_limit = settings.poster_max_response_bytes
        self.lock = asyncio.Lock()

    def _path(self, key: str) -> Path:
        return self.root / (hashlib.sha256(key.encode()).hexdigest() + ".img")

    async def get(self, key: str) -> bytes | None:
        async with self.lock:
            return await asyncio.to_thread(self._get, key)

    def _get(self, key: str) -> bytes | None:
        path = self._path(key)
        try:
            if path.is_symlink():
                return None
            info = path.stat()
            if info.st_size > self.item_limit or info.st_mtime + self.ttl <= time.time():
                return None
            return path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError:
            logger.warning("Poster cache read failed", exc_info=True)
            return None

    async def set(self, key: str, data: bytes) -> None:
        async with self.lock:
            await asyncio.to_thread(self._set, key, data)

    def _set(self, key: str, data: bytes) -> None:
        if len(data) > min(self.limit, self.item_limit):
            return
        path = self._path(key)
        temporary = self.root / f"{uuid.uuid4().hex}.tmp"
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            files = sorted(
                (
                    item
                    for item in self.root.glob("*.img")
                    if re.fullmatch(r"[a-f0-9]{64}\.img", item.name)
                    and not item.is_symlink()
                    and item.is_file()
                ),
                key=lambda item: item.stat().st_mtime,
            )
            total = sum(item.stat().st_size for item in files)
            for item in files:
                info = item.stat()
                if total + len(data) > self.limit or info.st_mtime + self.ttl <= time.time():
                    total -= info.st_size
                    item.unlink()
            with temporary.open("xb") as output:
                output.write(data)
            os.replace(temporary, path)
        except OSError:
            logger.warning("Poster cache write failed", exc_info=True)
