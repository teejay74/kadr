from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_playback_track_service
from app.core.config import Settings
from app.main import app
from app.models.library import LibraryItem
from app.models.torrent_task import TorrentTask
from app.repositories.library import LibraryRepository
from app.repositories.playback import PlaybackTrackPreferenceRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.playback import (
    PlaybackTrack,
    PlaybackTrackList,
    PlaybackTrackPreferenceRequest,
)
from app.services.playback.exceptions import (
    PlaybackTrackPreferenceError,
    PlaybackTrackProbeError,
)
from app.services.playback.tracks import (
    PlaybackTrackProbe,
    PlaybackTrackService,
    ProbedTracks,
)
from app.services.torrents.exceptions import TorrentFileError


class FakeProcess:
    returncode = 0

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    async def communicate(self) -> tuple[bytes, bytes]:
        return self.payload, b""

    def kill(self) -> None:
        return None

    async def wait(self) -> int:
        return self.returncode


class FakeProbe:
    def __init__(self, tracks: ProbedTracks | None = None) -> None:
        self.tracks = tracks or ProbedTracks(audio_tracks=[], subtitle_tracks=[])
        self.sources: list[Path] = []

    async def probe(self, source: Path) -> ProbedTracks:
        self.sources.append(source)
        return self.tracks


class FakeQBittorrent:
    def __init__(self, files: list[dict[str, Any]]) -> None:
        self._files = files

    async def files(self, _: str) -> list[dict[str, Any]]:
        return self._files


class FakeTrackEndpointService:
    async def torrent_tracks(
        self,
        task_id: str,
        profile_key: str = "default",
    ) -> PlaybackTrackList:
        del profile_key
        return PlaybackTrackList(
            source="torrent",
            source_id=task_id,
            file_id=7,
            audio_tracks=[sample_audio_track()],
        )

    async def library_tracks(
        self,
        item_id: str,
        profile_key: str = "default",
    ) -> PlaybackTrackList:
        del profile_key
        return PlaybackTrackList(
            source="library",
            source_id=item_id,
            file_id=7,
            subtitle_tracks=[sample_subtitle_track()],
        )

    async def save_torrent_preferences(
        self,
        task_id: str,
        request: PlaybackTrackPreferenceRequest,
    ) -> PlaybackTrackList:
        result = await self.torrent_tracks(task_id, request.profile_key)
        result.selected_audio_track_id = request.audio_track_id
        return result

    async def save_library_preferences(
        self,
        item_id: str,
        request: PlaybackTrackPreferenceRequest,
    ) -> PlaybackTrackList:
        result = await self.library_tracks(item_id, request.profile_key)
        result.selected_subtitle_track_id = request.subtitle_track_id
        result.subtitles_enabled = request.subtitles_enabled
        return result


def sample_audio_track() -> PlaybackTrack:
    return PlaybackTrack(
        id="a-one",
        preference_key="audio-semantic-key",
        stream_index=1,
        kind="audio",
        language="ru",
        codec="ac3",
        title="Студия",
        is_default=True,
        channels=6,
        channel_layout="5.1",
        delivery="native_or_compatible",
    )


def sample_subtitle_track() -> PlaybackTrack:
    return PlaybackTrack(
        id="s-one",
        preference_key="subtitle-semantic-key",
        stream_index=2,
        kind="subtitle",
        language="en",
        codec="subrip",
        title=None,
        is_forced=True,
        delivery="external_webvtt",
    )


def alternate_audio_track(
    track_id: str,
    preference_key: str,
    stream_index: int,
    language: str,
    title: str | None,
    *,
    is_default: bool = False,
) -> PlaybackTrack:
    return PlaybackTrack(
        id=track_id,
        preference_key=preference_key,
        stream_index=stream_index,
        kind="audio",
        language=language,
        codec="ac3",
        title=title,
        is_default=is_default,
        channels=2,
        channel_layout="stereo",
        delivery="native_or_compatible",
    )


def test_parse_ffprobe_tracks_normalizes_metadata_and_delivery() -> None:
    result = PlaybackTrackProbe.parse(
        {
            "streams": [
                {
                    "index": 1,
                    "codec_type": "audio",
                    "codec_name": "AC3",
                    "channels": 6,
                    "channel_layout": "5.1(side)",
                    "tags": {"language": "rus", "title": "  LostFilm\u0000  "},
                    "disposition": {"default": 1},
                },
                {
                    "index": 2,
                    "codec_type": "audio",
                    "codec_name": "eac3",
                    "channels": 2,
                    "tags": {"language": "eng"},
                    "disposition": {},
                },
                {
                    "index": 3,
                    "codec_type": "subtitle",
                    "codec_name": "subrip",
                    "tags": {"language": "en_US", "title": " SDH\n subtitles "},
                    "disposition": {"hearing_impaired": 1},
                },
                {
                    "index": 4,
                    "codec_type": "subtitle",
                    "codec_name": "hdmv_pgs_subtitle",
                    "tags": {"language": "ukr"},
                    "disposition": {"forced": 1},
                },
                {
                    "index": 5,
                    "codec_type": "subtitle",
                    "codec_name": "binary_data",
                    "tags": {"language": "../../unsafe"},
                    "disposition": {},
                },
            ]
        }
    )

    assert len(result.audio_tracks) == 2
    assert result.audio_tracks[0].model_dump() == {
        "id": result.audio_tracks[0].id,
        "preference_key": result.audio_tracks[0].preference_key,
        "stream_index": 1,
        "kind": "audio",
        "language": "ru",
        "codec": "ac3",
        "title": "LostFilm",
        "is_default": True,
        "is_forced": False,
        "is_hearing_impaired": False,
        "channels": 6,
        "channel_layout": "5.1(side)",
        "delivery": "native_or_compatible",
    }
    assert result.audio_tracks[1].title is None
    assert result.audio_tracks[1].language == "en"
    assert result.subtitle_tracks[0].language == "en-us"
    assert result.subtitle_tracks[0].title == "SDH subtitles"
    assert result.subtitle_tracks[0].is_hearing_impaired is True
    assert result.subtitle_tracks[0].delivery == "external_webvtt"
    assert result.subtitle_tracks[1].language == "uk"
    assert result.subtitle_tracks[1].is_forced is True
    assert result.subtitle_tracks[1].delivery == "burn_in_required"
    assert result.subtitle_tracks[2].language is None
    assert result.subtitle_tracks[2].delivery == "unsupported"
    assert result.audio_tracks[0].id != result.audio_tracks[0].preference_key


@pytest.mark.asyncio
async def test_probe_caches_unchanged_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "episode.mkv"
    source.write_bytes(b"video")
    calls: list[tuple[object, ...]] = []

    async def create_process(*args: object, **kwargs: object) -> FakeProcess:
        del kwargs
        calls.append(args)
        return FakeProcess(
            b'{"streams":[{"index":1,"codec_type":"audio",'
            b'"codec_name":"aac","tags":{"language":"eng"}}]}'
        )

    monkeypatch.setattr(
        "app.services.playback.tracks.asyncio.create_subprocess_exec",
        create_process,
    )
    probe = PlaybackTrackProbe(Settings())

    first = await probe.probe(source)
    second = await probe.probe(source)

    assert first is second
    assert first.audio_tracks[0].language == "en"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_torrent_tracks_require_complete_selected_file(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    download_root = tmp_path / "downloads"
    storage = download_root / "cache"
    storage.mkdir(parents=True)
    task = TorrentTask(
        id="00000000-0000-0000-0000-000000000701",
        media_id=77,
        media_kind="series",
        torrent_hash="track-hash",
        source_id="a" * 24,
        release_title="Series",
        selected_file_id=7,
        selected_file_path="Series.S01E07.mkv",
        storage_path=str(storage),
        state="downloading",
    )
    await TorrentTaskRepository(session).create(task)
    probe = FakeProbe()
    service = PlaybackTrackService(
        probe,  # type: ignore[arg-type]
        TorrentTaskRepository(session),
        LibraryRepository(session),
        FakeQBittorrent([{"index": 7, "progress": 0.99}]),  # type: ignore[arg-type]
        Settings(torrent_storage_root=str(download_root)),
        PlaybackTrackPreferenceRepository(session),
    )

    with pytest.raises(PlaybackTrackProbeError, match="finish downloading"):
        await service.torrent_tracks(task.id)

    assert probe.sources == []


@pytest.mark.asyncio
async def test_track_service_resolves_safe_torrent_and_library_sources(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    download_root = tmp_path / "downloads"
    storage = download_root / "cache"
    library_root = tmp_path / "library"
    storage.mkdir(parents=True)
    library_root.mkdir()
    task = TorrentTask(
        id="00000000-0000-0000-0000-000000000702",
        media_id=77,
        media_kind="series",
        torrent_hash="complete-track-hash",
        source_id="b" * 24,
        release_title="Series",
        selected_file_id=7,
        selected_file_path="Season 1/Series.S01E07.mkv",
        storage_path=str(storage),
        state="stoppedUP",
    )
    await TorrentTaskRepository(session).create(task)
    library_item = LibraryItem(
        id="00000000-0000-0000-0000-000000000703",
        task_id=task.id,
        file_id=7,
        media_id=77,
        media_kind="series",
        title="Series",
        original_title="Series",
        file_path=str(library_root / "Series.S01E07.mkv"),
        size_bytes=100,
    )
    await LibraryRepository(session).add_library(library_item)
    tracks = ProbedTracks(
        audio_tracks=[sample_audio_track()],
        subtitle_tracks=[sample_subtitle_track()],
    )
    probe = FakeProbe(tracks)
    service = PlaybackTrackService(
        probe,  # type: ignore[arg-type]
        TorrentTaskRepository(session),
        LibraryRepository(session),
        FakeQBittorrent([{"index": 7, "progress": 1}]),  # type: ignore[arg-type]
        Settings(
            torrent_storage_root=str(download_root),
            library_root=str(library_root),
        ),
        PlaybackTrackPreferenceRepository(session),
    )

    torrent_result = await service.torrent_tracks(task.id)
    library_result = await service.library_tracks(library_item.id)

    assert torrent_result.source == "torrent"
    assert torrent_result.file_id == 7
    assert library_result.source == "library"
    assert library_result.audio_tracks[0].title == "Студия"
    assert probe.sources == [
        storage / "Season 1" / "Series.S01E07.mkv",
        library_root / "Series.S01E07.mkv",
    ]


@pytest.mark.asyncio
async def test_torrent_tracks_reject_unsafe_relative_path(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    download_root = tmp_path / "downloads"
    download_root.mkdir()
    task = TorrentTask(
        id="00000000-0000-0000-0000-000000000704",
        media_id=77,
        media_kind="series",
        torrent_hash="unsafe-track-hash",
        source_id="c" * 24,
        release_title="Series",
        selected_file_id=7,
        selected_file_path="../outside.mkv",
        storage_path=str(download_root / "cache"),
        state="stoppedUP",
    )
    await TorrentTaskRepository(session).create(task)
    service = PlaybackTrackService(
        FakeProbe(),  # type: ignore[arg-type]
        TorrentTaskRepository(session),
        LibraryRepository(session),
        FakeQBittorrent([{"index": 7, "progress": 1}]),  # type: ignore[arg-type]
        Settings(torrent_storage_root=str(download_root)),
        PlaybackTrackPreferenceRepository(session),
    )

    with pytest.raises(TorrentFileError, match="unsafe"):
        await service.torrent_tracks(task.id)


@pytest.mark.asyncio
async def test_preferences_persist_by_profile_and_follow_semantic_track(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    download_root = tmp_path / "downloads"
    library_root = tmp_path / "library"
    download_root.mkdir()
    library_root.mkdir()
    task = TorrentTask(
        id="00000000-0000-0000-0000-000000000705",
        media_id=77,
        media_kind="series",
        torrent_hash="preference-track-hash",
        source_id="d" * 24,
        release_title="Series",
        selected_file_id=7,
        selected_file_path="Series.S01E07.mkv",
        storage_path=str(download_root),
        state="stoppedUP",
    )
    await TorrentTaskRepository(session).create(task)
    item = LibraryItem(
        id="00000000-0000-0000-0000-000000000706",
        task_id=task.id,
        file_id=7,
        media_id=77,
        media_kind="series",
        title="Series",
        original_title="Series",
        file_path=str(library_root / "Series.S01E07.mkv"),
        size_bytes=100,
    )
    await LibraryRepository(session).add_library(item)
    russian = alternate_audio_track("a-russian-1", "semantic-russian", 1, "ru", "Studio")
    english = alternate_audio_track(
        "a-english-1",
        "semantic-english",
        2,
        "en",
        None,
        is_default=True,
    )
    subtitle = sample_subtitle_track()
    probe = FakeProbe(ProbedTracks([russian, english], [subtitle]))
    service = PlaybackTrackService(
        probe,  # type: ignore[arg-type]
        TorrentTaskRepository(session),
        LibraryRepository(session),
        FakeQBittorrent([{"index": 7, "progress": 1}]),  # type: ignore[arg-type]
        Settings(
            torrent_storage_root=str(download_root),
            library_root=str(library_root),
        ),
        PlaybackTrackPreferenceRepository(session),
    )

    saved = await service.save_library_preferences(
        item.id,
        PlaybackTrackPreferenceRequest(
            profile_key="default",
            audio_track_id=russian.id,
            subtitle_track_id=subtitle.id,
            subtitles_enabled=True,
        ),
    )
    await service.save_library_preferences(
        item.id,
        PlaybackTrackPreferenceRequest(
            profile_key="guest",
            audio_track_id=english.id,
        ),
    )
    assert saved.selected_audio_track_id == russian.id
    assert saved.selected_subtitle_track_id == subtitle.id

    moved_russian = russian.model_copy(
        update={"id": "a-russian-9", "stream_index": 9}
    )
    moved_english = english.model_copy(
        update={"id": "a-english-8", "stream_index": 8}
    )
    probe.tracks = ProbedTracks([moved_english, moved_russian], [subtitle])

    default_result = await service.library_tracks(item.id, "default")
    guest_result = await service.library_tracks(item.id, "guest")

    assert default_result.selected_audio_track_id == moved_russian.id
    assert default_result.selected_subtitle_track_id == subtitle.id
    assert default_result.subtitles_enabled is True
    assert guest_result.selected_audio_track_id == moved_english.id
    assert guest_result.subtitles_enabled is False


@pytest.mark.asyncio
async def test_preference_rejects_track_from_another_file(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    download_root = tmp_path / "downloads"
    library_root = tmp_path / "library"
    download_root.mkdir()
    library_root.mkdir()
    task = TorrentTask(
        id="00000000-0000-0000-0000-000000000707",
        media_id=78,
        media_kind="movie",
        torrent_hash="invalid-preference-hash",
        source_id="e" * 24,
        release_title="Movie",
        selected_file_id=1,
        selected_file_path="Movie.mkv",
        storage_path=str(download_root),
        state="stoppedUP",
    )
    await TorrentTaskRepository(session).create(task)
    item = LibraryItem(
        id="00000000-0000-0000-0000-000000000708",
        task_id=task.id,
        file_id=1,
        media_id=78,
        media_kind="movie",
        title="Movie",
        original_title="Movie",
        file_path=str(library_root / "Movie.mkv"),
        size_bytes=100,
    )
    await LibraryRepository(session).add_library(item)
    service = PlaybackTrackService(
        FakeProbe(ProbedTracks([sample_audio_track()], [])),  # type: ignore[arg-type]
        TorrentTaskRepository(session),
        LibraryRepository(session),
        FakeQBittorrent([{"index": 1, "progress": 1}]),  # type: ignore[arg-type]
        Settings(
            torrent_storage_root=str(download_root),
            library_root=str(library_root),
        ),
        PlaybackTrackPreferenceRepository(session),
    )

    with pytest.raises(PlaybackTrackPreferenceError, match="does not belong"):
        await service.save_library_preferences(
            item.id,
            PlaybackTrackPreferenceRequest(audio_track_id="a-from-another-file"),
        )


@pytest.mark.asyncio
async def test_track_endpoints_return_source_specific_lists(client: AsyncClient) -> None:
    app.dependency_overrides[get_playback_track_service] = FakeTrackEndpointService

    torrent_response = await client.get("/api/v1/torrents/task-1/tracks")
    library_response = await client.get("/api/v1/library/item-1/tracks")
    save_torrent_response = await client.put(
        "/api/v1/torrents/task-1/tracks/preferences",
        json={"audio_track_id": "a-one"},
    )
    save_library_response = await client.put(
        "/api/v1/library/item-1/tracks/preferences",
        json={
            "subtitle_track_id": "s-one",
            "subtitles_enabled": True,
        },
    )

    assert torrent_response.status_code == 200
    assert torrent_response.json()["audio_tracks"][0]["language"] == "ru"
    assert library_response.status_code == 200
    assert library_response.json()["subtitle_tracks"][0]["is_forced"] is True
    assert save_torrent_response.json()["selected_audio_track_id"] == "a-one"
    assert save_library_response.json()["selected_subtitle_track_id"] == "s-one"

