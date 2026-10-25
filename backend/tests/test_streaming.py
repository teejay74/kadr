from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import AsyncClient

from app.api.dependencies import get_streaming_manager
from app.core.config import Settings
from app.main import app
from app.models.torrent_task import TorrentTask
from app.services.streaming.exceptions import (
    StreamBufferTimeoutError,
    StreamLimitError,
    StreamRangeError,
)
from app.services.streaming.manager import StreamingManager, media_type_for
from app.services.streaming.ranges import parse_byte_range
from app.services.streaming.registry import StreamRegistry

VIDEO = b"0123456789abcdef"


class FakeRepository:
    def __init__(self, task: TorrentTask) -> None:
        self.task = task

    async def get(self, task_id: str) -> TorrentTask | None:
        return self.task if task_id == self.task.id else None


class FakeTorrentManager:
    def __init__(self, speed: int = 0) -> None:
        self.started = 0
        self.speed = speed

    async def start(self, task_id: str) -> Any:
        self.started += 1
        return SimpleNamespace(download_speed_bytes=self.speed)


class FakeQBittorrent:
    def __init__(
        self,
        *,
        progress: float = 1,
        states: list[list[int]] | None = None,
    ) -> None:
        self.progress = progress
        self.states = states or [[2, 2, 2, 2, 2]]
        self.state_calls = 0
        self.priority_calls: list[tuple[list[int], int]] = []
        self.streaming_mode_calls = 0

    async def files(self, torrent_hash: str) -> list[dict[str, Any]]:
        return [
            {"index": 0, "name": "padding.bin", "size": 4, "progress": 1},
            {
                "index": 1,
                "name": "video.mp4",
                "size": len(VIDEO),
                "progress": self.progress,
                "piece_range": [1, 4],
            },
        ]

    async def properties(self, torrent_hash: str) -> dict[str, Any]:
        return {"piece_size": 4}

    async def piece_states(self, torrent_hash: str) -> list[int]:
        value = self.states[min(self.state_calls, len(self.states) - 1)]
        self.state_calls += 1
        return value

    async def set_file_priority(
        self, torrent_hash: str, file_ids: list[int], priority: int
    ) -> None:
        self.priority_calls.append((file_ids, priority))

    async def prepare_for_streaming(self, torrent_hash: str) -> None:
        self.streaming_mode_calls += 1


def make_manager(
    tmp_path: Path,
    *,
    qbit: FakeQBittorrent | None = None,
    registry: StreamRegistry | None = None,
    timeout: float = 0.05,
) -> tuple[StreamingManager, FakeTorrentManager, StreamRegistry]:
    (tmp_path / "video.mp4").write_bytes(VIDEO)
    task = TorrentTask(
        id="task-1",
        media_id=42,
        media_kind="movie",
        torrent_hash="abc123",
        source_id="a" * 24,
        release_title="Test video",
        selected_file_id=1,
        selected_file_path="video.mp4",
        storage_path=str(tmp_path),
        state="stoppedDL",
    )
    torrent_manager = FakeTorrentManager(speed=4)
    stream_registry = registry or StreamRegistry(2)
    settings = Settings(
        torrent_storage_root=str(tmp_path),
        torrent_save_path=str(tmp_path),
        stream_start_buffer_mb=1,
        stream_chunk_size_kb=64,
        stream_poll_interval_seconds=0.01,
        stream_read_timeout_seconds=timeout,
    )
    manager = StreamingManager(
        qbit or FakeQBittorrent(),  # type: ignore[arg-type]
        torrent_manager,  # type: ignore[arg-type]
        FakeRepository(task),  # type: ignore[arg-type]
        stream_registry,
        settings,
    )
    return manager, torrent_manager, stream_registry


async def read_all(content: Any) -> bytes:
    return b"".join([chunk async for chunk in content])


def test_byte_range_parser_supports_full_open_and_suffix_ranges() -> None:
    assert parse_byte_range(None, 16).length == 16
    assert parse_byte_range("bytes=4-7", 16).start == 4
    assert parse_byte_range("bytes=8-", 16).end == 15
    assert parse_byte_range("bytes=-4", 16).start == 12


def test_video_media_types_do_not_depend_on_container_mime_database() -> None:
    assert media_type_for(Path("video.mkv")) == "video/x-matroska"
    assert media_type_for(Path("video.mp4")) == "video/mp4"


@pytest.mark.parametrize("value", ["bytes=20-30", "items=0-1", "bytes=1-0", "bytes=0-1,3-4"])
def test_byte_range_parser_rejects_unsatisfiable_ranges(value: str) -> None:
    with pytest.raises(StreamRangeError):
        parse_byte_range(value, 16)


async def test_streams_complete_file_and_releases_session(tmp_path: Path) -> None:
    manager, torrents, registry = make_manager(tmp_path)

    prepared = await manager.open("task-1", None)

    assert await read_all(prepared.content) == VIDEO
    assert prepared.byte_range.partial is False
    assert prepared.media_type == "video/mp4"
    assert torrents.started == 0
    assert await registry.active_count() == 0


async def test_forward_and_backward_seek_ranges(tmp_path: Path) -> None:
    manager, _, _ = make_manager(tmp_path)

    forward = await manager.open("task-1", "bytes=8-11")
    backward = await manager.open("task-1", "bytes=2-5")

    assert await read_all(forward.content) == VIDEO[8:12]
    assert await read_all(backward.content) == VIDEO[2:6]


async def test_waits_for_incomplete_pieces_and_starts_torrent(tmp_path: Path) -> None:
    qbit = FakeQBittorrent(progress=0.25, states=[[0, 0, 0, 0, 0], [2, 2, 2, 2, 2]])
    manager, torrents, _ = make_manager(tmp_path, qbit=qbit)

    prepared = await manager.open("task-1", "bytes=0-3")

    assert await read_all(prepared.content) == VIDEO[:4]
    assert torrents.started == 1
    assert qbit.state_calls >= 2
    assert qbit.streaming_mode_calls == 1
    assert qbit.priority_calls == [([1], 1)]


async def test_readiness_starts_download_and_reports_required_pieces(
    tmp_path: Path,
) -> None:
    qbit = FakeQBittorrent(progress=0.25, states=[[0, 2, 0, 2, 0]])
    manager, torrents, _ = make_manager(tmp_path, qbit=qbit)

    readiness = await manager.readiness("task-1")

    assert readiness.ready is False
    assert readiness.buffer_progress == 0.5
    assert torrents.started == 1
    assert qbit.streaming_mode_calls == 1


async def test_readiness_reports_complete_file_as_playable(tmp_path: Path) -> None:
    manager, torrents, _ = make_manager(tmp_path)

    readiness = await manager.readiness("task-1")

    assert readiness.ready is True
    assert readiness.buffer_progress == 1
    assert torrents.started == 0


def test_initial_buffer_adapts_to_speed_and_caps_at_configured_target(
    tmp_path: Path,
) -> None:
    manager, _, _ = make_manager(tmp_path)
    manager._settings.stream_start_buffer_mb = 32
    manager._settings.stream_chunk_size_kb = 1024
    large_range = 128 * 1024**2

    assert manager._initial_buffer_bytes(large_range, 0) == 1 * 1024**2
    assert manager._initial_buffer_bytes(large_range, 2 * 1024**2) == 8 * 1024**2
    assert manager._initial_buffer_bytes(large_range, 20 * 1024**2) == 32 * 1024**2


async def test_times_out_when_requested_pieces_are_unavailable(tmp_path: Path) -> None:
    qbit = FakeQBittorrent(progress=0.1, states=[[0, 0, 0, 0, 0]])
    manager, _, registry = make_manager(tmp_path, qbit=qbit, timeout=0.02)

    with pytest.raises(StreamBufferTimeoutError):
        await manager.open("task-1", "bytes=0-3")

    assert await registry.active_count() == 0


async def test_disconnect_releases_active_stream_and_allows_reconnect(tmp_path: Path) -> None:
    manager, _, registry = make_manager(tmp_path)
    first = await manager.open("task-1", None)
    content = first.content

    assert await anext(content) == VIDEO
    assert await registry.active_count() == 1
    await content.aclose()
    assert await registry.active_count() == 0

    reconnect = await manager.open("task-1", "bytes=0-3")
    assert await read_all(reconnect.content) == VIDEO[:4]


async def test_unstarted_response_can_release_its_stream_lease(tmp_path: Path) -> None:
    manager, _, registry = make_manager(tmp_path)
    prepared = await manager.open("task-1", "bytes=0-3")

    assert await registry.active_count() == 1
    await prepared.release()
    assert await registry.active_count() == 0


async def test_parallel_ranges_for_one_task_share_a_stream_slot(tmp_path: Path) -> None:
    registry = StreamRegistry(2, requests_per_task=3)
    manager, _, _ = make_manager(tmp_path, registry=registry)
    first = await manager.open("task-1", None)
    second = await manager.open("task-1", None)
    third = await manager.open("task-1", None)

    with pytest.raises(StreamLimitError):
        await manager.open("task-1", None)

    assert await registry.active_count() == 1
    await anext(first.content)
    await first.content.aclose()
    await anext(second.content)
    await second.content.aclose()
    await anext(third.content)
    await third.content.aclose()
    assert await registry.active_count() == 0


async def test_enforces_distinct_stream_task_limit() -> None:
    registry = StreamRegistry(2)
    first = await registry.acquire("task-1")
    parallel_range = await registry.acquire("task-1")
    second = await registry.acquire("task-2")

    assert await registry.active_count() == 2
    with pytest.raises(StreamLimitError):
        await registry.acquire("task-3")

    await first.release()
    await parallel_range.release()
    await second.release()
    assert await registry.active_count() == 0


async def test_stream_endpoint_returns_200_206_and_416(
    client: AsyncClient, tmp_path: Path
) -> None:
    manager, _, _ = make_manager(tmp_path)
    app.dependency_overrides[get_streaming_manager] = lambda: manager

    full = await client.get("/api/v1/torrents/task-1/stream")
    partial = await client.get(
        "/api/v1/torrents/task-1/stream", headers={"Range": "bytes=4-7"}
    )
    invalid = await client.get(
        "/api/v1/torrents/task-1/stream", headers={"Range": "bytes=99-100"}
    )

    assert full.status_code == 200
    assert full.headers["accept-ranges"] == "bytes"
    assert full.content == VIDEO
    assert partial.status_code == 206
    assert partial.headers["content-range"] == "bytes 4-7/16"
    assert partial.headers["content-length"] == "4"
    assert partial.content == VIDEO[4:8]
    assert invalid.status_code == 416
    assert invalid.headers["content-range"] == "bytes */16"


async def test_stream_readiness_endpoint(client: AsyncClient, tmp_path: Path) -> None:
    manager, _, _ = make_manager(tmp_path)
    app.dependency_overrides[get_streaming_manager] = lambda: manager

    response = await client.get("/api/v1/torrents/task-1/stream/readiness")

    assert response.status_code == 200
    assert response.json() == {"ready": True, "buffer_progress": 1.0}
