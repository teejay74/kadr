from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.schemas.playback import PlaybackTrack
from app.services.playback.exceptions import PlaybackSubtitleError

ARTIFACT_PATTERN = re.compile(r"^[a-f0-9]{32}$")


@dataclass(frozen=True)
class PreparedSubtitle:
    artifact_id: str
    path: Path


class SubtitleManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._semaphore = asyncio.Semaphore(settings.max_active_transcodes)
        self._locks: dict[str, asyncio.Lock] = {}

    async def prepare(
        self,
        source: Path,
        source_kind: str,
        source_id: str,
        track: PlaybackTrack,
    ) -> PreparedSubtitle:
        if track.kind != "subtitle" or track.delivery != "external_webvtt":
            raise PlaybackSubtitleError("The selected subtitle cannot be delivered as WebVTT")
        try:
            stat = await asyncio.to_thread(source.stat)
        except OSError as exc:
            raise PlaybackSubtitleError("The selected video file is unavailable") from exc
        identity = "\0".join(
            (str(source), str(stat.st_size), str(stat.st_mtime_ns), track.id)
        )
        artifact_id = hashlib.sha256(identity.encode()).hexdigest()[:32]
        source_key = hashlib.sha256(f"{source_kind}\0{source_id}".encode()).hexdigest()[:24]
        directory = Path(self._settings.playback_cache_root) / "subtitles" / source_key
        target = directory / f"{artifact_id}.vtt"
        if await asyncio.to_thread(target.is_file):
            return PreparedSubtitle(artifact_id, target)

        lock = self._locks.setdefault(artifact_id, asyncio.Lock())
        async with lock:
            if await asyncio.to_thread(target.is_file):
                return PreparedSubtitle(artifact_id, target)
            await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
            temporary = directory / f".{artifact_id}-{uuid.uuid4().hex}.tmp"
            async with self._semaphore:
                await self._extract(source, track.stream_index, temporary)
            try:
                await asyncio.to_thread(temporary.replace, target)
            except OSError as exc:
                await asyncio.to_thread(temporary.unlink, missing_ok=True)
                raise PlaybackSubtitleError("Could not publish the subtitle file") from exc
        self._locks.pop(artifact_id, None)
        return PreparedSubtitle(artifact_id, target)

    async def open(self, source_kind: str, source_id: str, artifact_id: str) -> Path:
        if not ARTIFACT_PATTERN.fullmatch(artifact_id):
            raise PlaybackSubtitleError("The subtitle artifact ID is invalid")
        source_key = hashlib.sha256(f"{source_kind}\0{source_id}".encode()).hexdigest()[:24]
        root = Path(self._settings.playback_cache_root) / "subtitles" / source_key
        target = root / f"{artifact_id}.vtt"
        if not await asyncio.to_thread(target.is_file):
            raise PlaybackSubtitleError("The prepared subtitle is unavailable")
        return target

    async def _extract(self, source: Path, stream_index: int, target: Path) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                self._settings.ffmpeg_path,
                "-nostdin",
                "-y",
                "-v",
                "error",
                "-i",
                str(source),
                "-map",
                f"0:{stream_index}",
                "-c:s",
                "webvtt",
                "-f",
                "webvtt",
                str(target),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise PlaybackSubtitleError("FFmpeg is unavailable") from exc
        try:
            _, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self._settings.subtitle_extraction_timeout_seconds,
            )
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            await asyncio.to_thread(target.unlink, missing_ok=True)
            raise PlaybackSubtitleError("Subtitle preparation timed out") from exc
        if process.returncode != 0:
            await asyncio.to_thread(target.unlink, missing_ok=True)
            detail = stderr.decode(errors="replace").strip() or "FFmpeg failed"
            raise PlaybackSubtitleError(detail.replace(str(source), source.name))
