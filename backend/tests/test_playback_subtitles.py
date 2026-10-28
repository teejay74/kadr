from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from app.schemas.playback import PlaybackTrack
from app.services.playback.exceptions import PlaybackSubtitleError
from app.services.playback.subtitles import SubtitleManager


class FakeFFmpegProcess:
    returncode = 0

    def __init__(self, target: Path) -> None:
        self._target = target

    async def communicate(self) -> tuple[bytes, bytes]:
        self._target.write_text("WEBVTT\n", encoding="utf-8")
        return b"", b""

    def kill(self) -> None:
        return None

    async def wait(self) -> int:
        return self.returncode


def subtitle_track(*, delivery: str = "external_webvtt") -> PlaybackTrack:
    return PlaybackTrack(
        id="s-opaque",
        preference_key="semantic",
        stream_index=4,
        kind="subtitle",
        language="ru",
        codec="subrip",
        delivery=delivery,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_extracts_exact_text_track_and_reuses_cached_webvtt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.mkv"
    source.write_bytes(b"video")
    calls: list[tuple[Any, ...]] = []

    async def create_process(*args: Any, **_: Any) -> FakeFFmpegProcess:
        calls.append(args)
        return FakeFFmpegProcess(Path(args[-1]))

    monkeypatch.setattr("asyncio.create_subprocess_exec", create_process)
    manager = SubtitleManager(Settings(playback_cache_root=str(tmp_path / "cache")))

    first = await manager.prepare(source, "torrent", "task/id", subtitle_track())
    second = await manager.prepare(source, "torrent", "task/id", subtitle_track())

    assert first == second
    assert first.path.read_text(encoding="utf-8") == "WEBVTT\n"
    assert len(calls) == 1
    assert calls[0][calls[0].index("-map") + 1] == "0:4"
    assert calls[0][calls[0].index("-c:s") + 1] == "webvtt"
    assert await manager.open("torrent", "task/id", first.artifact_id) == first.path


@pytest.mark.asyncio
async def test_rejects_bitmap_and_unsafe_artifact_ids(tmp_path: Path) -> None:
    source = tmp_path / "source.mkv"
    source.write_bytes(b"video")
    manager = SubtitleManager(Settings(playback_cache_root=str(tmp_path / "cache")))

    with pytest.raises(PlaybackSubtitleError, match="WebVTT"):
        await manager.prepare(
            source,
            "torrent",
            "task",
            subtitle_track(delivery="burn_in_required"),
        )
    with pytest.raises(PlaybackSubtitleError, match="invalid"):
        await manager.open("torrent", "task", "../../unsafe")
