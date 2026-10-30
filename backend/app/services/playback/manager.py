from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

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
    task_id: str | None = None
    selected_file_id: int | None = None
    source: Path | None = None
    mode: PlaybackMode = "compatible"
    audio_stream_index: int | None = None
    track_id: str | None = None


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
        self._queue: list[str] = []
        self._lock = asyncio.Lock()

    async def start(
        self,
        task_id: str,
        selected_file_id: int,
        source: Path,
        mode: PlaybackMode = "compatible",
        audio_stream_index: int | None = None,
        track_id: str | None = None,
    ) -> PlaybackPreparation:
        self._validate_track_mode(mode, audio_stream_index, track_id)
        job_id = self._job_id(task_id, selected_file_id, mode, track_id)
        output = self._output_path(task_id, selected_file_id, mode, track_id)
        if await asyncio.to_thread(output.is_file):
            job = self._jobs.setdefault(job_id, PreparationJob())
            job.state = "ready"
            job.progress = 1.0
            return self._to_status(
                task_id,
                selected_file_id,
                mode,
                job,
                track_id,
            )

        async with self._lock:
            current = self._jobs.get(job_id)
            if current is not None and (
                current.state == "queued"
                or (current.task is not None and not current.task.done())
            ):
                return self._to_status(
                    task_id,
                    selected_file_id,
                    mode,
                    current,
                    track_id,
                )
            if len(self._queue) >= self._settings.max_queued_transcodes:
                raise PlaybackPreparationLimitError(
                    "The compatible-playback preparation queue is full"
                )
            await self._ensure_output_space(source)
            job = PreparationJob(
                state="queued",
                task_id=task_id,
                selected_file_id=selected_file_id,
                source=source,
                mode=mode,
                audio_stream_index=audio_stream_index,
                track_id=track_id,
            )
            self._jobs[job_id] = job
            self._queue.append(job_id)
            self._start_available_locked()
            return self._to_status(
                task_id,
                selected_file_id,
                mode,
                job,
                track_id,
            )

    def status(
        self,
        task_id: str,
        selected_file_id: int,
        mode: PlaybackMode = "compatible",
        track_id: str | None = None,
    ) -> PlaybackPreparation:
        self._validate_track_mode(mode, None, track_id, preparing=False)
        job = self._jobs.get(self._job_id(task_id, selected_file_id, mode, track_id))
        output = self._output_path(task_id, selected_file_id, mode, track_id)
        if job is None:
            if output.is_file():
                job = PreparationJob(state="ready", progress=1.0)
            else:
                job = PreparationJob()
        return self._to_status(
            task_id,
            selected_file_id,
            mode,
            job,
            track_id,
        )

    async def cancel(
        self,
        task_id: str,
        selected_file_id: int,
        mode: PlaybackMode = "compatible",
        track_id: str | None = None,
    ) -> PlaybackPreparation:
        self._validate_track_mode(mode, None, track_id, preparing=False)
        job_id = self._job_id(task_id, selected_file_id, mode, track_id)
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return PlaybackPreparation(mode=mode, state="idle", progress=0)
            if job.state != "queued":
                raise PlaybackPreparationError(
                    "Only a queued compatible-playback preparation can be cancelled"
                )
            self._queue.remove(job_id)
            self._jobs.pop(job_id, None)
            return PlaybackPreparation(
                mode=mode,
                state="idle",
                progress=0,
                track_id=track_id,
            )

    async def open(
        self,
        task_id: str,
        selected_file_id: int,
        mode: PlaybackMode,
        range_header: str | None,
        registry: StreamRegistry,
        track_id: str | None = None,
    ) -> PreparedStream:
        self._validate_track_mode(mode, None, track_id, preparing=False)
        output = self._output_path(task_id, selected_file_id, mode, track_id)
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
        self._queue.clear()
        tasks = [job.task for job in self._jobs.values() if job.task is not None]
        for job in self._jobs.values():
            if job.process is not None and job.process.returncode is None:
                job.process.terminate()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _start_available_locked(self) -> None:
        running = sum(
            job.task is not None and not job.task.done()
            for job in self._jobs.values()
        )
        while running < self._settings.max_active_transcodes and self._queue:
            job_id = self._queue.pop(0)
            job = self._jobs.get(job_id)
            if (
                job is None
                or job.task_id is None
                or job.selected_file_id is None
                or job.source is None
            ):
                continue
            job.state = "probing"
            job.task = asyncio.create_task(self._execute_job(job_id, job))
            running += 1

    async def _execute_job(self, job_id: str, job: PreparationJob) -> None:
        assert job.task_id is not None
        assert job.selected_file_id is not None
        assert job.source is not None
        try:
            await self._run(
                job.task_id,
                job.selected_file_id,
                job.source,
                job.mode,
                job,
                job.audio_stream_index,
                job.track_id,
            )
        finally:
            async with self._lock:
                if self._jobs.get(job_id) is job:
                    job.task = None
                self._start_available_locked()

    def is_preparing(self, task_id: str, selected_file_id: int) -> bool:
        prefix = f"{task_id}:{selected_file_id}:"
        return any(
            key.startswith(prefix)
            and (
                job.state == "queued"
                or (job.task is not None and not job.task.done())
            )
            for key, job in self._jobs.items()
        )

    def is_task_preparing(self, task_id: str) -> bool:
        prefix = f"{task_id}:"
        return any(
            key.startswith(prefix)
            and (
                job.state == "queued"
                or (job.task is not None and not job.task.done())
            )
            for key, job in self._jobs.items()
        )

    async def discard_task(self, task_id: str) -> None:
        if self.is_task_preparing(task_id):
            raise PlaybackPreparationError(
                "Stop compatible playback preparation before deleting this download"
            )
        prefix = f"{task_id}:"
        for key in [key for key in self._jobs if key.startswith(prefix)]:
            self._jobs.pop(key, None)
        root = Path(self._settings.playback_cache_root).resolve(strict=False)
        directory = (root / task_id).resolve(strict=False)
        if not directory.is_relative_to(root):
            raise PlaybackPreparationError("The playback cache path is unsafe")
        if await asyncio.to_thread(directory.is_dir):
            await asyncio.to_thread(shutil.rmtree, directory)

    async def discard(self, task_id: str, selected_file_id: int) -> None:
        if self.is_preparing(task_id, selected_file_id):
            raise PlaybackPreparationError(
                "Stop compatible playback preparation before deleting this video"
            )
        directory = self._output_path(
            task_id,
            selected_file_id,
            "compatible",
        ).parent
        outputs = [directory / "compatible.mp4", directory / "audio-only.mp4"]
        if await asyncio.to_thread(directory.is_dir):
            outputs.extend(
                await asyncio.to_thread(lambda: list(directory.glob("audio-*.mp4")))
            )
        prefix = f"{task_id}:{selected_file_id}:"
        for key in [key for key in self._jobs if key.startswith(prefix)]:
            self._jobs.pop(key, None)
        for output in outputs:
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
        audio_stream_index: int | None,
        track_id: str | None,
    ) -> None:
        temporary = self._output_path(task_id, selected_file_id, mode, track_id).with_suffix(
            ".part.mp4"
        )
        try:
            probe = await self._probe(source, audio_stream_index)
            job.video_codec = probe.video_codec
            job.audio_codec = probe.audio_codec
            job.strategy = (
                "audio_transcode"
                if mode in {"audio_only", "audio_track"}
                else select_strategy(probe)
            )
            job.state = "processing"
            output = self._output_path(task_id, selected_file_id, mode, track_id)
            await asyncio.to_thread(output.parent.mkdir, parents=True, exist_ok=True)
            command = self._ffmpeg_command(
                source,
                temporary,
                job.strategy,
                probe.video_codec,
                audio_stream_index,
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

    async def _probe(
        self,
        source: Path,
        audio_stream_index: int | None = None,
    ) -> ProbeResult:
        try:
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
        except OSError as exc:
            raise PlaybackPreparationError("ffprobe is unavailable") from exc
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self._settings.ffprobe_timeout_seconds,
            )
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise PlaybackPreparationError("ffprobe timed out") from exc
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
            (
                item
                for item in streams
                if item.get("codec_type") == "audio"
                and (
                    audio_stream_index is None
                    or item.get("index") == audio_stream_index
                )
            ),
            None,
        )
        if not isinstance(video, dict):
            raise PlaybackPreparationError("The selected file has no video stream")
        if audio_stream_index is not None and not isinstance(audio, dict):
            raise PlaybackPreparationError("The selected audio stream is unavailable")
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
        audio_stream_index: int | None = None,
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
            (
                f"0:{audio_stream_index}"
                if audio_stream_index is not None
                else "0:a:0?"
            ),
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
            pending_sources = [
                job.source
                for job in self._jobs.values()
                if job.source is not None
                and job.state in {"queued", "probing", "processing"}
            ]
            pending_bytes = 0
            for pending_source in pending_sources:
                pending_bytes += (
                    await asyncio.to_thread(pending_source.stat)
                ).st_size
        except OSError as exc:
            raise PlaybackPreparationError(
                "The compatible-playback cache is unavailable"
            ) from exc
        reserve = int(self._settings.playback_min_free_space_gb * 1024**3)
        if usage.free < source_size + pending_bytes + reserve:
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
    def _job_id(
        task_id: str,
        selected_file_id: int,
        mode: PlaybackMode,
        track_id: str | None = None,
    ) -> str:
        return f"{task_id}:{selected_file_id}:{mode}:{track_id or '-'}"

    def _output_path(
        self,
        task_id: str,
        selected_file_id: int,
        mode: PlaybackMode,
        track_id: str | None = None,
    ) -> Path:
        if not task_id or Path(task_id).name != task_id:
            raise PlaybackPreparationError("Invalid playback task identifier")
        if selected_file_id < 0:
            raise PlaybackPreparationError("Invalid selected file identifier")
        root = Path(self._settings.playback_cache_root).resolve(strict=False)
        if mode == "compatible":
            filename = "compatible.mp4"
        elif mode == "audio_only":
            filename = "audio-only.mp4"
        else:
            self._validate_track_id(track_id)
            filename = f"audio-{track_id}.mp4"
        output = (
            root / task_id / str(selected_file_id) / filename
        ).resolve(strict=False)
        if not output.is_relative_to(root):
            raise PlaybackPreparationError("Playback output is outside KADR cache")
        return output

    def _to_status(
        self,
        task_id: str,
        selected_file_id: int,
        mode: PlaybackMode,
        job: PreparationJob,
        track_id: str | None = None,
    ) -> PlaybackPreparation:
        job_id = self._job_id(task_id, selected_file_id, mode, track_id)
        queue_position = None
        if job.state == "queued" and job_id in self._queue:
            queue_position = self._queue.index(job_id) + 1
        return PlaybackPreparation(
            mode=mode,
            state=job.state,
            progress=job.progress,
            strategy=job.strategy,
            video_codec=job.video_codec,
            audio_codec=job.audio_codec,
            message=job.message,
            track_id=track_id,
            queue_position=queue_position,
            stream_url=(
                f"/api/v1/torrents/{task_id}/compatible/stream"
                + self._stream_query(mode, track_id)
                if job.state == "ready"
                else None
            ),
        )

    @staticmethod
    def _stream_query(mode: PlaybackMode, track_id: str | None) -> str:
        if mode == "audio_only":
            return "?mode=audio_only"
        if mode == "audio_track" and track_id is not None:
            return f"?mode=audio_track&track_id={quote(track_id)}"
        return ""

    @staticmethod
    def _validate_track_id(track_id: str | None) -> None:
        if (
            track_id is None
            or len(track_id) > 64
            or not all(
                character.isalnum() or character == "-" for character in track_id
            )
        ):
            raise PlaybackPreparationError("Invalid audio track identifier")

    @classmethod
    def _validate_track_mode(
        cls,
        mode: PlaybackMode,
        audio_stream_index: int | None,
        track_id: str | None,
        *,
        preparing: bool = True,
    ) -> None:
        if mode != "audio_track":
            return
        cls._validate_track_id(track_id)
        if preparing and (audio_stream_index is None or audio_stream_index < 0):
            raise PlaybackPreparationError("Invalid selected audio stream")

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
