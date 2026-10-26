from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import Settings
from app.schemas.playback import (
    PlaybackMode,
    PlaybackPreparation,
    PlaybackState,
    PlaybackStrategy,
)
from app.services.playback.exceptions import (
    PlaybackArtifactNotReadyError,
    PlaybackPreparationError,
    PlaybackPreparationLimitError,
)
from app.services.streaming.manager import PreparedStream
from app.services.streaming.ranges import parse_byte_range
from app.services.streaming.registry import StreamLease, StreamRegistry

logger = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    duration_seconds: float
    video_codec: str
    video_profile: str
    pixel_format: str
    audio_codec: str | None
    audio_profile: str | None


@dataclass
class PreparationJob:
    state: PlaybackState = "idle"
    progress: float = 0.0
    strategy: PlaybackStrategy | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    message: str | None = None
    task: asyncio.Task[None] | None = None
    process: asyncio.subprocess.Process | None = None
    stderr: list[str] = field(default_factory=list)


def select_strategy(probe: ProbeResult) -> PlaybackStrategy:
    copy_video = probe.video_codec == "h264" and probe.pixel_format in {
        "yuv420p",
        "yuvj420p",
    }
    copy_audio = probe.audio_codec in {None, "aac"} and (
        probe.audio_codec is None or (probe.audio_profile or "").lower() == "lc"
    )
    if copy_video and copy_audio:
        return "remux"
    if copy_video:
        return "audio_transcode"
    return "transcode"


class CompatibilityManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jobs: dict[str, PreparationJob] = {}
        self._lock = asyncio.Lock()

    async def start(
        self,
        task_id: str,
        selected_file_id: int,
        source: Path,
        mode: PlaybackMode = "compatible",
    ) -> PlaybackPreparation:
        job_id = self._job_id(task_id, selected_file_id, mode)
        output = self._output_path(task_id, selected_file_id, mode)
        if await asyncio.to_thread(output.is_file):
            job = self._jobs.setdefault(job_id, PreparationJob())
            job.state = "ready"
            job.progress = 1.0
            return self._to_status(task_id, mode, job)

        async with self._lock:
            current = self._jobs.get(job_id)
            if current is not None and current.task is not None and not current.task.done():
                return self._to_status(task_id, mode, current)
            running = sum(
                job.task is not None and not job.task.done()
                for job in self._jobs.values()
            )
            if running >= self._settings.max_active_transcodes:
                raise PlaybackPreparationLimitError(
                    "The compatible-playback preparation limit has been reached"
                )
            job = PreparationJob(state="probing")
            await self._ensure_output_space(source)
            self._jobs[job_id] = job
            job.task = asyncio.create_task(
                self._run(task_id, selected_file_id, source, mode, job)
            )
            return self._to_status(task_id, mode, job)

    def status(
        self,
        task_id: str,
        selected_file_id: int,
        mode: PlaybackMode = "compatible",
    ) -> PlaybackPreparation:
        job = self._jobs.get(self._job_id(task_id, selected_file_id, mode))
        output = self._output_path(task_id, selected_file_id, mode)
        if job is None:
            if output.is_file():
                job = PreparationJob(state="ready", progress=1.0)
            else:
                job = PreparationJob()
        return self._to_status(task_id, mode, job)

    async def open(
        self,
        task_id: str,
        selected_file_id: int,
        mode: PlaybackMode,
        range_header: str | None,
        registry: StreamRegistry,
    ) -> PreparedStream:
        output = self._output_path(task_id, selected_file_id, mode)
        if not await asyncio.to_thread(output.is_file):
            raise PlaybackArtifactNotReadyError(
                "The compatible playback file is not ready"
            )
        size = (await asyncio.to_thread(output.stat)).st_size
        byte_range = parse_byte_range(range_header, size)
        # Direct Play and its compatible fallback are one viewer session. They
        # must share the same registry slot while the browser switches sources.
        lease = await registry.acquire(task_id)
        return PreparedStream(
            content=self._read(output, byte_range.start, byte_range.end, lease),
            byte_range=byte_range,
            media_type="video/mp4",
            filename=output.name,
            release=lease.release,
        )

    async def close(self) -> None:
        tasks = [job.task for job in self._jobs.values() if job.task is not None]
        for job in self._jobs.values():
            if job.process is not None and job.process.returncode is None:
                job.process.terminate()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def is_preparing(self, task_id: str, selected_file_id: int) -> bool:
        return any(
            (job := self._jobs.get(self._job_id(task_id, selected_file_id, mode)))
            is not None
            and job.task is not None
            and not job.task.done()
            for mode in ("compatible", "audio_only")
        )

    async def discard(self, task_id: str, selected_file_id: int) -> None:
        if self.is_preparing(task_id, selected_file_id):
            raise PlaybackPreparationError(
                "Stop compatible playback preparation before deleting this video"
            )
        outputs = [
            self._output_path(task_id, selected_file_id, mode)
            for mode in ("compatible", "audio_only")
        ]
        for mode, output in zip(("compatible", "audio_only"), outputs, strict=True):
            self._jobs.pop(self._job_id(task_id, selected_file_id, mode), None)
            await asyncio.to_thread(output.unlink, missing_ok=True)
            await asyncio.to_thread(output.with_suffix(".part.mp4").unlink, missing_ok=True)
        try:
            await asyncio.to_thread(outputs[0].parent.rmdir)
        except OSError:
            pass

    async def _run(
        self,
        task_id: str,
        selected_file_id: int,
        source: Path,
        mode: PlaybackMode,
        job: PreparationJob,
    ) -> None:
        temporary = self._output_path(task_id, selected_file_id, mode).with_suffix(
            ".part.mp4"
        )
        try:
            probe = await self._probe(source)
            job.video_codec = probe.video_codec
            job.audio_codec = probe.audio_codec
            job.strategy = (
                "audio_transcode" if mode == "audio_only" else select_strategy(probe)
            )
            job.state = "processing"
            output = self._output_path(task_id, selected_file_id, mode)
            await asyncio.to_thread(output.parent.mkdir, parents=True, exist_ok=True)
            command = self._ffmpeg_command(
                source,
                temporary,
                job.strategy,
                probe.video_codec,
            )
            job.process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stderr_task = asyncio.create_task(self._collect_stderr(job))
            assert job.process.stdout is not None
            while line := await job.process.stdout.readline():
                key, _, value = line.decode(errors="replace").strip().partition("=")
                if key in {"out_time_us", "out_time_ms"} and probe.duration_seconds > 0:
                    seconds = int(value or 0) / 1_000_000
                    job.progress = min(max(seconds / probe.duration_seconds, 0), 0.99)
            return_code = await job.process.wait()
            await stderr_task
            if return_code != 0:
                detail = job.stderr[-1] if job.stderr else "FFmpeg failed"
                raise PlaybackPreparationError(detail)
            await asyncio.to_thread(os.replace, temporary, output)
            job.progress = 1.0
            job.state = "ready"
            job.message = None
        except asyncio.CancelledError:
            if job.process is not None and job.process.returncode is None:
                job.process.terminate()
                await job.process.wait()
            await self._remove_temporary(temporary)
            raise
        except (OSError, ValueError, json.JSONDecodeError, PlaybackPreparationError) as exc:
            job.state = "failed"
            job.message = str(exc).replace(str(source), source.name)
            logger.warning(
                "Compatible playback preparation failed for task %s: %s",
                task_id,
                job.message,
            )
            await self._remove_temporary(temporary)

    async def _probe(self, source: Path) -> ProbeResult:
        process = await asyncio.create_subprocess_exec(
            self._settings.ffprobe_path,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(source),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise PlaybackPreparationError(
                stderr.decode(errors="replace").strip() or "ffprobe failed"
            )
        payload = json.loads(stdout)
        streams = payload.get("streams") or []
        video = next(
            (item for item in streams if item.get("codec_type") == "video"),
            None,
        )
        audio = next(
            (item for item in streams if item.get("codec_type") == "audio"),
            None,
        )
        if not isinstance(video, dict):
            raise PlaybackPreparationError("The selected file has no video stream")
        duration = float((payload.get("format") or {}).get("duration") or 0)
        return ProbeResult(
            duration_seconds=max(duration, 0),
            video_codec=str(video.get("codec_name") or "unknown").lower(),
            video_profile=str(video.get("profile") or "unknown"),
            pixel_format=str(video.get("pix_fmt") or "unknown").lower(),
            audio_codec=(
                str(audio.get("codec_name") or "unknown").lower()
                if isinstance(audio, dict)
                else None
            ),
            audio_profile=(
                str(audio.get("profile") or "unknown")
                if isinstance(audio, dict)
                else None
            ),
        )

    def _ffmpeg_command(
        self,
        source: Path,
        output: Path,
        strategy: PlaybackStrategy,
        video_codec: str | None = None,
    ) -> list[str]:
        command = [
            self._settings.ffmpeg_path,
            "-hide_banner",
            "-nostdin",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-sn",
            "-dn",
        ]
        if strategy in {"remux", "audio_transcode"}:
            command.extend(["-c:v", "copy"])
            if video_codec == "hevc":
                command.extend(["-tag:v", "hvc1"])
        else:
            command.extend(
                [
                    "-c:v",
                    "libx264",
                    "-preset",
                    self._settings.transcode_video_preset,
                    "-crf",
                    str(self._settings.transcode_video_crf),
                    "-pix_fmt",
                    "yuv420p",
                    "-vf",
                    (
                        f"scale='min({self._settings.transcode_max_width},iw)':"
                        f"'min({self._settings.transcode_max_height},ih)':"
                        "force_original_aspect_ratio=decrease:force_divisible_by=2"
                    ),
                    "-threads",
                    str(self._settings.transcode_video_threads),
                ]
            )
        if strategy == "remux":
            command.extend(["-c:a", "copy"])
        else:
            command.extend(
                [
                    "-c:a",
                    "aac",
                    "-profile:a",
                    "aac_low",
                    "-b:a",
                    self._settings.transcode_audio_bitrate,
                    "-ac",
                    "2",
                ]
            )
        command.extend(
            [
                "-movflags",
                "+faststart",
                "-progress",
                "pipe:1",
                str(output),
            ]
        )
        return command

    async def _ensure_output_space(self, source: Path) -> None:
        root = Path(self._settings.playback_cache_root).resolve(strict=False)
        try:
            await asyncio.to_thread(root.mkdir, parents=True, exist_ok=True)
            usage = await asyncio.to_thread(shutil.disk_usage, root)
            source_size = (await asyncio.to_thread(source.stat)).st_size
        except OSError as exc:
            raise PlaybackPreparationError(
                "The compatible-playback cache is unavailable"
            ) from exc
        reserve = int(self._settings.playback_min_free_space_gb * 1024**3)
        if usage.free < source_size + reserve:
            raise PlaybackPreparationError(
                "Not enough free space to prepare a compatible playback file"
            )

    async def _collect_stderr(self, job: PreparationJob) -> None:
        assert job.process is not None and job.process.stderr is not None
        while line := await job.process.stderr.readline():
            job.stderr.append(line.decode(errors="replace").strip())
            if len(job.stderr) > 20:
                del job.stderr[0]

    async def _remove_temporary(self, temporary: Path) -> None:
        try:
            await asyncio.to_thread(temporary.unlink, missing_ok=True)
        except OSError as exc:
            logger.warning("Could not remove incomplete playback artifact: %s", exc)

    @staticmethod
    def _job_id(task_id: str, selected_file_id: int, mode: PlaybackMode) -> str:
        return f"{task_id}:{selected_file_id}:{mode}"

    def _output_path(
        self,
        task_id: str,
        selected_file_id: int,
        mode: PlaybackMode,
    ) -> Path:
        if not task_id or Path(task_id).name != task_id:
            raise PlaybackPreparationError("Invalid playback task identifier")
        if selected_file_id < 0:
            raise PlaybackPreparationError("Invalid selected file identifier")
        root = Path(self._settings.playback_cache_root).resolve(strict=False)
        filename = "compatible.mp4" if mode == "compatible" else "audio-only.mp4"
        output = (
            root / task_id / str(selected_file_id) / filename
        ).resolve(strict=False)
        if not output.is_relative_to(root):
            raise PlaybackPreparationError("Playback output is outside KADR cache")
        return output

    def _to_status(
        self,
        task_id: str,
        mode: PlaybackMode,
        job: PreparationJob,
    ) -> PlaybackPreparation:
        return PlaybackPreparation(
            mode=mode,
            state=job.state,
            progress=job.progress,
            strategy=job.strategy,
            video_codec=job.video_codec,
            audio_codec=job.audio_codec,
            message=job.message,
            stream_url=(
                f"/api/v1/torrents/{task_id}/compatible/stream"
                + ("?mode=audio_only" if mode == "audio_only" else "")
                if job.state == "ready"
                else None
            ),
        )

    async def _read(
        self,
        path: Path,
        start: int,
        end: int,
        lease: StreamLease,
    ) -> AsyncIterator[bytes]:
        file = None
        offset = start
        chunk_size = self._settings.stream_chunk_size_kb * 1024
        try:
            file = await asyncio.to_thread(path.open, "rb")
            await asyncio.to_thread(file.seek, start)
            while offset <= end:
                length = min(chunk_size, end - offset + 1)
                chunk = await asyncio.to_thread(file.read, length)
                if not chunk:
                    break
                offset += len(chunk)
                yield chunk
        finally:
            if file is not None:
                await asyncio.to_thread(file.close)
            await lease.release()
