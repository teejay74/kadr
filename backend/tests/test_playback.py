from pathlib import Path

from app.core.config import Settings
from app.services.playback.manager import (
    CompatibilityManager,
    ProbeResult,
    select_strategy,
)
from app.services.streaming.registry import StreamRegistry


def probe(
    video: str = "h264",
    audio: str | None = "aac",
    *,
    audio_profile: str | None = "LC",
    pixel_format: str = "yuv420p",
) -> ProbeResult:
    return ProbeResult(
        duration_seconds=60,
        video_codec=video,
        video_profile="High",
        pixel_format=pixel_format,
        audio_codec=audio,
        audio_profile=audio_profile,
    )


def test_strategy_prefers_remux_then_audio_only_then_full_transcode() -> None:
    assert select_strategy(probe()) == "remux"
    assert select_strategy(probe(audio="ac3", audio_profile=None)) == "audio_transcode"
    assert select_strategy(probe(audio_profile="HE-AAC")) == "audio_transcode"
    assert select_strategy(probe(video="hevc")) == "transcode"
    assert select_strategy(probe(pixel_format="yuv420p10le")) == "transcode"


def test_ffmpeg_command_never_reencodes_compatible_video(tmp_path: Path) -> None:
    manager = CompatibilityManager(Settings(playback_cache_root=str(tmp_path)))

    command = manager._ffmpeg_command(
        Path("input.mkv"),
        Path("output.part.mp4"),
        "audio_transcode",
        "hevc",
    )

    assert command[0] == "ffmpeg"
    assert command[command.index("-c:v") + 1] == "copy"
    assert command[command.index("-c:a") + 1] == "aac"
    assert command[command.index("-tag:v") + 1] == "hvc1"
    assert "-nostdin" in command
    assert "-map_metadata" in command
    assert "-sn" in command
    assert "-dn" in command


def test_ffmpeg_command_bounds_incompatible_video_conversion(tmp_path: Path) -> None:
    manager = CompatibilityManager(
        Settings(
            playback_cache_root=str(tmp_path),
            transcode_video_threads=2,
            transcode_max_width=1920,
            transcode_max_height=1080,
        )
    )

    command = manager._ffmpeg_command(
        Path("input.mkv"),
        Path("output.part.mp4"),
        "transcode",
    )

    assert command[command.index("-c:v") + 1] == "libx264"
    assert command[command.index("-pix_fmt") + 1] == "yuv420p"
    assert command[command.index("-threads") + 1] == "2"
    assert "min(1920,iw)" in command[command.index("-vf") + 1]
    assert "min(1080,ih)" in command[command.index("-vf") + 1]
    assert command[command.index("-c:a") + 1] == "aac"
    assert command[command.index("-ac") + 1] == "2"


async def test_ready_compatible_file_supports_byte_ranges(tmp_path: Path) -> None:
    task_id = "task-1"
    selected_file_id = 3
    output = tmp_path / task_id / str(selected_file_id) / "compatible.mp4"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"0123456789")
    manager = CompatibilityManager(
        Settings(playback_cache_root=str(tmp_path), stream_chunk_size_kb=64)
    )
    registry = StreamRegistry(2)

    status = manager.status(task_id, selected_file_id)
    direct_lease = await registry.acquire(task_id)
    prepared = await manager.open(
        task_id,
        selected_file_id,
        "compatible",
        "bytes=2-5",
        registry,
    )
    assert await registry.active_count() == 1
    content = b"".join([chunk async for chunk in prepared.content])

    assert status.state == "ready"
    assert status.stream_url == "/api/v1/torrents/task-1/compatible/stream"
    assert prepared.media_type == "video/mp4"
    assert prepared.byte_range.start == 2
    assert prepared.byte_range.end == 5
    assert content == b"2345"
    assert await registry.active_count() == 1
    await direct_lease.release()
    assert await registry.active_count() == 0


def test_compatible_files_are_isolated_by_selected_torrent_file(tmp_path: Path) -> None:
    task_id = "task-1"
    first = tmp_path / task_id / "1" / "compatible.mp4"
    first.parent.mkdir(parents=True)
    first.write_bytes(b"first episode")
    manager = CompatibilityManager(Settings(playback_cache_root=str(tmp_path)))

    first_status = manager.status(task_id, 1)
    third_status = manager.status(task_id, 3)

    assert first_status.state == "ready"
    assert third_status.state == "idle"


def test_audio_only_artifact_is_separate_from_full_compatibility(
    tmp_path: Path,
) -> None:
    task_id = "task-1"
    directory = tmp_path / task_id / "1"
    directory.mkdir(parents=True)
    (directory / "audio-only.mp4").write_bytes(b"fast")
    manager = CompatibilityManager(Settings(playback_cache_root=str(tmp_path)))

    fast = manager.status(task_id, 1, "audio_only")
    full = manager.status(task_id, 1, "compatible")

    assert fast.state == "ready"
    assert fast.mode == "audio_only"
    assert fast.stream_url == (
        "/api/v1/torrents/task-1/compatible/stream?mode=audio_only"
    )
    assert full.state == "idle"
