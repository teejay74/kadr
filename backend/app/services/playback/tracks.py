from __future__ import annotations

import asyncio
import hashlib
import json
import re
import stat as stat_module
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from app.core.config import Settings
from app.models.library import LibraryItem
from app.models.playback import PlaybackTrackPreference
from app.models.torrent_task import TorrentTask
from app.repositories.library import LibraryRepository
from app.repositories.playback import PlaybackTrackPreferenceRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.playback import (
    PlaybackSource,
    PlaybackTrack,
    PlaybackTrackList,
    PlaybackTrackPreferenceRequest,
)
from app.services.library.exceptions import LibraryNotFoundError, LibraryStorageError
from app.services.playback.exceptions import (
    PlaybackTrackPreferenceError,
    PlaybackTrackProbeError,
)
from app.services.playback.subtitles import PreparedSubtitle, SubtitleManager
from app.services.torrents.exceptions import TorrentFileError, TorrentNotFoundError
from app.services.torrents.qbittorrent import QBittorrentClient

LANGUAGE_ALIASES = {
    "ara": "ar",
    "ces": "cs",
    "chi": "zh",
    "cze": "cs",
    "deu": "de",
    "dut": "nl",
    "eng": "en",
    "fra": "fr",
    "fre": "fr",
    "ger": "de",
    "hin": "hi",
    "ita": "it",
    "jpn": "ja",
    "kor": "ko",
    "nld": "nl",
    "pol": "pl",
    "por": "pt",
    "rus": "ru",
    "spa": "es",
    "tur": "tr",
    "ukr": "uk",
    "zho": "zh",
}
TEXT_SUBTITLE_CODECS = {"ass", "mov_text", "ssa", "subrip", "text", "webvtt"}
IMAGE_SUBTITLE_CODECS = {
    "dvb_subtitle",
    "dvd_subtitle",
    "hdmv_pgs_subtitle",
    "xsub",
}
LANGUAGE_PATTERN = re.compile(r"^[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8})*$")


@dataclass(frozen=True)
class ProbedTracks:
    audio_tracks: list[PlaybackTrack]
    subtitle_tracks: list[PlaybackTrack]


class PlaybackTrackProbe:
    def __init__(self, settings: Settings, cache_size: int = 128) -> None:
        self._settings = settings
        self._cache_size = cache_size
        self._cache: OrderedDict[tuple[str, int, int], ProbedTracks] = OrderedDict()

    async def probe(self, source: Path) -> ProbedTracks:
        try:
            stat = await asyncio.to_thread(source.stat)
        except OSError as exc:
            raise PlaybackTrackProbeError("The selected video file is unavailable") from exc
        if not stat_module.S_ISREG(stat.st_mode) or stat.st_size <= 0:
            raise PlaybackTrackProbeError("The selected video file is unavailable")
        cache_key = (str(source), stat.st_size, stat.st_mtime_ns)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
            return cached

        try:
            process = await asyncio.create_subprocess_exec(
                self._settings.ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                (
                    "stream=index,codec_type,codec_name,profile,channels,channel_layout:"
                    "stream_tags=language,title:"
                    "stream_disposition=default,forced,hearing_impaired"
                ),
                "-of",
                "json",
                str(source),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise PlaybackTrackProbeError("ffprobe is unavailable") from exc
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self._settings.ffprobe_timeout_seconds,
            )
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise PlaybackTrackProbeError("ffprobe timed out while inspecting tracks") from exc
        if process.returncode != 0:
            detail = stderr.decode(errors="replace").strip() or "ffprobe failed"
            raise PlaybackTrackProbeError(detail.replace(str(source), source.name))
        try:
            payload = json.loads(stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PlaybackTrackProbeError("ffprobe returned invalid track metadata") from exc
        result = self.parse(payload)
        self._cache[cache_key] = result
        self._cache.move_to_end(cache_key)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return result

    @classmethod
    def parse(cls, payload: Any) -> ProbedTracks:
        if not isinstance(payload, dict) or not isinstance(payload.get("streams"), list):
            raise PlaybackTrackProbeError("ffprobe returned invalid track metadata")
        audio_tracks: list[PlaybackTrack] = []
        subtitle_tracks: list[PlaybackTrack] = []
        for item in payload["streams"]:
            if not isinstance(item, dict):
                continue
            kind = item.get("codec_type")
            if kind not in {"audio", "subtitle"}:
                continue
            try:
                stream_index = int(item.get("index"))
            except (TypeError, ValueError):
                continue
            if stream_index < 0:
                continue
            codec = (cls._clean(item.get("codec_name"), 64) or "unknown").lower()
            tags = item.get("tags") if isinstance(item.get("tags"), dict) else {}
            disposition = (
                item.get("disposition")
                if isinstance(item.get("disposition"), dict)
                else {}
            )
            language = cls._language(tags.get("language"))
            title = cls._clean(tags.get("title"), 200)
            channels = cls._positive_int(item.get("channels")) if kind == "audio" else None
            channel_layout = (
                cls._clean(item.get("channel_layout"), 64) if kind == "audio" else None
            )
            is_default = bool(disposition.get("default"))
            is_forced = bool(disposition.get("forced"))
            is_hearing_impaired = bool(disposition.get("hearing_impaired"))
            semantic = "\0".join(
                (
                    str(kind),
                    language or "und",
                    (title or "").casefold(),
                    codec,
                    str(channels or ""),
                    (channel_layout or "").casefold(),
                    str(int(is_default)),
                    str(int(is_forced)),
                    str(int(is_hearing_impaired)),
                )
            )
            preference_key = hashlib.sha256(semantic.encode()).hexdigest()
            exact = f"{semantic}\0{stream_index}"
            track_id = f"{str(kind)[0]}-{hashlib.sha256(exact.encode()).hexdigest()[:20]}"
            if kind == "audio":
                delivery = "native_or_compatible" if codec != "unknown" else "unsupported"
            elif codec in TEXT_SUBTITLE_CODECS:
                delivery = "external_webvtt"
            elif codec in IMAGE_SUBTITLE_CODECS:
                delivery = "burn_in_required"
            else:
                delivery = "unsupported"
            track = PlaybackTrack(
                id=track_id,
                preference_key=preference_key,
                stream_index=stream_index,
                kind=kind,
                language=language,
                codec=codec,
                title=title,
                is_default=is_default,
                is_forced=is_forced,
                is_hearing_impaired=is_hearing_impaired,
                channels=channels,
                channel_layout=channel_layout,
                delivery=delivery,
            )
            (audio_tracks if kind == "audio" else subtitle_tracks).append(track)
        return ProbedTracks(audio_tracks=audio_tracks, subtitle_tracks=subtitle_tracks)

    @staticmethod
    def _clean(value: Any, limit: int) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = " ".join(value.replace("\x00", " ").split()).strip()
        return cleaned[:limit] or None

    @staticmethod
    def _language(value: Any) -> str | None:
        cleaned = PlaybackTrackProbe._clean(value, 35)
        if cleaned is None or cleaned.casefold() in {"und", "unknown"}:
            return None
        normalized = cleaned.replace("_", "-").lower()
        normalized = LANGUAGE_ALIASES.get(normalized, normalized)
        return normalized if LANGUAGE_PATTERN.fullmatch(normalized) else None

    @staticmethod
    def _positive_int(value: Any) -> int | None:
        try:
            result = int(value)
        except (TypeError, ValueError):
            return None
        return result if result > 0 else None


class PlaybackTrackService:
    def __init__(
        self,
        probe: PlaybackTrackProbe,
        tasks: TorrentTaskRepository,
        library: LibraryRepository,
        client: QBittorrentClient,
        settings: Settings,
        preferences: PlaybackTrackPreferenceRepository,
        subtitles: SubtitleManager | None = None,
    ) -> None:
        self._probe = probe
        self._tasks = tasks
        self._library = library
        self._client = client
        self._settings = settings
        self._preferences = preferences
        self._subtitles = subtitles

    async def torrent_tracks(
        self,
        task_id: str,
        profile_key: str = "default",
    ) -> PlaybackTrackList:
        task, tracks = await self._probe_torrent(task_id)
        return await self._track_list(
            "torrent",
            task.id,
            task.selected_file_id,
            tracks,
            profile_key,
        )

    async def save_torrent_preferences(
        self,
        task_id: str,
        request: PlaybackTrackPreferenceRequest,
    ) -> PlaybackTrackList:
        task, tracks = await self._probe_torrent(task_id)
        preference = await self._save_preference(request, tracks)
        return self._track_list_with_preference(
            "torrent",
            task.id,
            task.selected_file_id,
            tracks,
            preference,
        )

    async def prepare_torrent_subtitle(
        self,
        task_id: str,
        track_id: str,
    ) -> PreparedSubtitle:
        task, tracks = await self._probe_torrent(task_id)
        track = self._find_requested(tracks.subtitle_tracks, track_id, "subtitle")
        if track is None or self._subtitles is None:
            raise PlaybackTrackPreferenceError("The selected subtitle is unavailable")
        source = self._safe_torrent_source(task.storage_path, task.selected_file_path or "")
        return await self._subtitles.prepare(source, "torrent", task.id, track)

    async def open_torrent_subtitle(self, task_id: str, artifact_id: str) -> Path:
        if self._subtitles is None:
            raise PlaybackTrackPreferenceError("The selected subtitle is unavailable")
        return await self._subtitles.open("torrent", task_id, artifact_id)

    async def _probe_torrent(self, task_id: str) -> tuple[TorrentTask, ProbedTracks]:
        task = await self._tasks.get(task_id)
        if task is None:
            raise TorrentNotFoundError("Torrent task not found")
        if task.selected_file_id is None or task.selected_file_path is None:
            raise TorrentFileError("Select a video file before inspecting tracks")
        files = await self._client.files(task.torrent_hash)
        selected = next(
            (
                item
                for index, item in enumerate(files)
                if int(item.get("index", index)) == task.selected_file_id
            ),
            None,
        )
        if selected is None:
            raise TorrentFileError("The selected video is no longer in the torrent")
        if float(selected.get("progress") or 0) < 1:
            raise PlaybackTrackProbeError(
                "The selected video must finish downloading before track inspection"
            )
        source = self._safe_torrent_source(task.storage_path, task.selected_file_path)
        tracks = await self._probe.probe(source)
        return task, tracks

    async def library_tracks(
        self,
        item_id: str,
        profile_key: str = "default",
    ) -> PlaybackTrackList:
        item, tracks = await self._probe_library(item_id)
        return await self._track_list(
            "library",
            item.id,
            item.file_id,
            tracks,
            profile_key,
        )

    async def save_library_preferences(
        self,
        item_id: str,
        request: PlaybackTrackPreferenceRequest,
    ) -> PlaybackTrackList:
        item, tracks = await self._probe_library(item_id)
        preference = await self._save_preference(request, tracks)
        return self._track_list_with_preference(
            "library",
            item.id,
            item.file_id,
            tracks,
            preference,
        )

    async def prepare_library_subtitle(
        self,
        item_id: str,
        track_id: str,
    ) -> PreparedSubtitle:
        item, tracks = await self._probe_library(item_id)
        track = self._find_requested(tracks.subtitle_tracks, track_id, "subtitle")
        if track is None or self._subtitles is None:
            raise PlaybackTrackPreferenceError("The selected subtitle is unavailable")
        source = self._safe_library_source(item.file_path)
        return await self._subtitles.prepare(source, "library", item.id, track)

    async def open_library_subtitle(self, item_id: str, artifact_id: str) -> Path:
        if self._subtitles is None:
            raise PlaybackTrackPreferenceError("The selected subtitle is unavailable")
        return await self._subtitles.open("library", item_id, artifact_id)

    async def _probe_library(self, item_id: str) -> tuple[LibraryItem, ProbedTracks]:
        item = await self._library.get_library(item_id)
        if item is None:
            raise LibraryNotFoundError("Library item not found")
        source = self._safe_library_source(item.file_path)
        tracks = await self._probe.probe(source)
        return item, tracks

    async def _track_list(
        self,
        source: PlaybackSource,
        source_id: str,
        file_id: int | None,
        tracks: ProbedTracks,
        profile_key: str,
    ) -> PlaybackTrackList:
        preference = await self._preferences.get(profile_key)
        return self._track_list_with_preference(
            source,
            source_id,
            file_id,
            tracks,
            preference,
        )

    def _track_list_with_preference(
        self,
        source: PlaybackSource,
        source_id: str,
        file_id: int | None,
        tracks: ProbedTracks,
        preference: PlaybackTrackPreference | None,
    ) -> PlaybackTrackList:
        audio = self._resolve_track(tracks.audio_tracks, preference, "audio")
        subtitles_enabled = bool(preference and preference.subtitles_enabled)
        subtitle = (
            self._resolve_track(tracks.subtitle_tracks, preference, "subtitle")
            if subtitles_enabled
            else None
        )
        return PlaybackTrackList(
            source=source,
            source_id=source_id,
            file_id=file_id,
            audio_tracks=tracks.audio_tracks,
            subtitle_tracks=tracks.subtitle_tracks,
            selected_audio_track_id=audio.id if audio else None,
            selected_subtitle_track_id=subtitle.id if subtitle else None,
            subtitles_enabled=subtitles_enabled,
        )

    async def _save_preference(
        self,
        request: PlaybackTrackPreferenceRequest,
        tracks: ProbedTracks,
    ) -> PlaybackTrackPreference:
        audio = self._find_requested(tracks.audio_tracks, request.audio_track_id, "audio")
        subtitle = self._find_requested(
            tracks.subtitle_tracks,
            request.subtitle_track_id,
            "subtitle",
        )
        preference = await self._preferences.get(request.profile_key)
        if preference is None:
            preference = PlaybackTrackPreference(
                id=str(uuid.uuid4()),
                profile_key=request.profile_key,
            )
        if audio is not None:
            self._assign_track(preference, audio, "audio")
        if subtitle is not None:
            self._assign_track(preference, subtitle, "subtitle")
        preference.subtitles_enabled = request.subtitles_enabled
        return await self._preferences.save(preference)

    @staticmethod
    def _find_requested(
        tracks: list[PlaybackTrack],
        track_id: str | None,
        kind: str,
    ) -> PlaybackTrack | None:
        if track_id is None:
            return None
        track = next((item for item in tracks if item.id == track_id), None)
        if track is None:
            raise PlaybackTrackPreferenceError(
                f"The selected {kind} track does not belong to this file"
            )
        return track

    @staticmethod
    def _assign_track(
        preference: PlaybackTrackPreference,
        track: PlaybackTrack,
        kind: str,
    ) -> None:
        setattr(preference, f"{kind}_preference_key", track.preference_key)
        setattr(preference, f"{kind}_language", track.language)
        setattr(preference, f"{kind}_title", track.title)
        setattr(preference, f"{kind}_codec", track.codec)

    @staticmethod
    def _resolve_track(
        tracks: list[PlaybackTrack],
        preference: PlaybackTrackPreference | None,
        kind: str,
    ) -> PlaybackTrack | None:
        if not tracks:
            return None
        if preference is None:
            return next((track for track in tracks if track.is_default), tracks[0])
        key = getattr(preference, f"{kind}_preference_key")
        language = getattr(preference, f"{kind}_language")
        title = getattr(preference, f"{kind}_title")
        codec = getattr(preference, f"{kind}_codec")
        if key:
            exact = next((track for track in tracks if track.preference_key == key), None)
            if exact is not None:
                return exact
        candidates = tracks
        for attributes in (
            ("language", "title", "codec"),
            ("language", "title"),
            ("language", "codec"),
            ("language",),
        ):
            expected = {
                "language": language,
                "title": title,
                "codec": codec,
            }
            if any(expected[name] is None for name in attributes):
                continue
            match = next(
                (
                    track
                    for track in candidates
                    if all(
                        PlaybackTrackService._same(
                            getattr(track, name),
                            expected[name],
                        )
                        for name in attributes
                    )
                ),
                None,
            )
            if match is not None:
                return match
        return next((track for track in tracks if track.is_default), tracks[0])

    @staticmethod
    def _same(first: str | None, second: str | None) -> bool:
        return (
            first is not None
            and second is not None
            and first.casefold() == second.casefold()
        )

    def _safe_torrent_source(self, storage_path: str, relative_path: str) -> Path:
        relative = PurePosixPath(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise TorrentFileError("The selected video path is unsafe")
        try:
            root = Path(self._settings.torrent_storage_root).resolve(strict=True)
            storage = Path(storage_path).resolve(strict=False)
            source = (storage / Path(*relative.parts)).resolve(strict=False)
        except OSError as exc:
            raise PlaybackTrackProbeError("KADR download storage is unavailable") from exc
        if not storage.is_relative_to(root) or not source.is_relative_to(root):
            raise TorrentFileError("The selected video is outside KADR storage")
        return source

    def _safe_library_source(self, value: str) -> Path:
        try:
            root = Path(self._settings.library_root).resolve(strict=True)
            source = Path(value).resolve(strict=False)
        except OSError as exc:
            raise LibraryStorageError("KADR library storage is unavailable") from exc
        if not source.is_relative_to(root):
            raise LibraryStorageError("The saved video is outside KADR library storage")
        return source
