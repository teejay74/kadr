from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import PurePosixPath
from typing import Literal, cast

from app.models.episodes import EpisodeFileBinding, MediaEpisode
from app.models.torrent_task import TorrentTask
from app.repositories.episodes import EpisodeRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.episode_matcher import (
    EpisodeMatchConfirmationRequest,
    EpisodeMatchFile,
    EpisodeMatchIdentity,
    EpisodeMatchReport,
    MatchConfidence,
)
from app.schemas.media import EpisodeSummary
from app.schemas.torrents import TorrentFile
from app.services.metadata.catalog import CatalogService
from app.services.metadata.exceptions import MetadataError
from app.services.torrents.exceptions import TorrentFileError, TorrentNotFoundError
from app.services.torrents.manager import TorrentManager

_DASHES = "-–—"
_TECHNICAL_WORDS = {
    "1080p",
    "2160p",
    "720p",
    "bluray",
    "bdrip",
    "dl",
    "dvdrip",
    "h264",
    "h265",
    "hevc",
    "mkv",
    "mp4",
    "proper",
    "remux",
    "repack",
    "web",
    "webrip",
    "x264",
    "x265",
}


@dataclass(frozen=True, order=True)
class EpisodeKey:
    season: int
    episode: int


@dataclass(frozen=True)
class ParsedPath:
    episodes: tuple[EpisodeKey, ...]
    season_hint: int | None
    explicit: bool
    unsafe: bool
    reason: str


class EpisodeMatcher:
    def __init__(
        self,
        catalog: CatalogService,
        torrents: TorrentManager,
        tasks: TorrentTaskRepository,
        episodes: EpisodeRepository,
    ) -> None:
        self._catalog = catalog
        self._torrents = torrents
        self._tasks = tasks
        self._episodes = episodes

    async def analyze(self, task_id: str) -> EpisodeMatchReport:
        task = await self._task(task_id)
        files = [item for item in await self._torrents.files(task_id) if item.is_video]
        existing_rows = await self._episodes.list_task_bindings(task_id)
        existing: dict[int, list[tuple[EpisodeFileBinding, MediaEpisode]]] = defaultdict(list)
        for binding, episode, variant in existing_rows:
            existing[variant.file_id].append((binding, episode))

        parsed = {item.id: self.parse_path(item.name) for item in files}
        seasons = {
            key.season
            for result in parsed.values()
            for key in result.episodes
        }
        seasons.update(
            result.season_hint
            for result in parsed.values()
            if result.season_hint is not None
        )
        release_season = self.parse_path(f"{task.release_title}/episode.mkv").season_hint
        if release_season is not None:
            seasons.add(release_season)

        metadata, metadata_available = await self._metadata(task, seasons)
        if not seasons and metadata_available:
            regular_seasons = await self._regular_seasons(task)
            if len(regular_seasons) == 1:
                metadata, metadata_available = await self._metadata(task, regular_seasons)

        proposed = {
            item.id: self._proposal(item, parsed[item.id], metadata, metadata_available)
            for item in files
            if item.id not in existing
        }
        conflicts = Counter(
            (episode.season_number, episode.episode_number)
            for match in proposed.values()
            if match.confidence == "exact"
            for episode in match.episodes
        )
        confirmed_keys = {
            (episode.season_number, episode.episode_number)
            for rows in existing.values()
            for _, episode in rows
        }

        results: list[EpisodeMatchFile] = []
        for item in files:
            if item.id in existing:
                results.append(self._existing_match(item, existing[item.id], metadata))
                continue
            match = proposed[item.id]
            has_conflict = any(
                conflicts[(episode.season_number, episode.episode_number)] > 1
                or (episode.season_number, episode.episode_number) in confirmed_keys
                for episode in match.episodes
            )
            if match.confidence == "exact" and has_conflict:
                match = match.model_copy(
                    update={
                        "confidence": "ambiguous",
                        "reasons": [*match.reasons, "Эпизод также сопоставлен другому файлу."],
                    }
                )
            elif match.confidence == "exact" and match.episodes:
                await self._episodes.replace_file_bindings(
                    task,
                    item.id,
                    item.name,
                    [
                        (
                            episode.season_number,
                            episode.episode_number,
                            episode.catalog_episode_id,
                        )
                        for episode in match.episodes
                    ],
                    confidence="exact",
                    confirmation="automatic",
                )
                match = match.model_copy(
                    update={"confirmed": True, "confirmation": "automatic"}
                )
            results.append(match)

        return EpisodeMatchReport(
            task_id=task.id,
            metadata_available=metadata_available,
            files=results,
            requires_confirmation=any(not item.confirmed for item in results),
        )

    async def confirm(
        self,
        task_id: str,
        request: EpisodeMatchConfirmationRequest,
    ) -> EpisodeMatchReport:
        task = await self._task(task_id)
        files = {item.id: item for item in await self._torrents.files(task_id)}
        seasons = {
            episode.season_number
            for mapping in request.mappings
            for episode in mapping.episodes
        }
        metadata, metadata_available = await self._metadata(task, seasons)
        if not metadata_available:
            raise TorrentFileError(
                "Episode metadata is unavailable; retry before confirming mappings"
            )

        for mapping in request.mappings:
            item = files.get(mapping.file_id)
            if item is None or not item.is_video:
                raise TorrentFileError("A confirmed torrent file does not exist or is not video")
            if self.parse_path(item.name).unsafe:
                raise TorrentFileError("An unsafe torrent path cannot be matched")
            keys = [
                EpisodeKey(episode.season_number, episode.episode_number)
                for episode in mapping.episodes
            ]
            if any(key not in metadata for key in keys):
                raise TorrentFileError("A confirmed episode does not exist in TMDB metadata")
            parsed = self.parse_path(item.name)
            confidence = "exact" if set(keys) == set(parsed.episodes) else "ambiguous"
            await self._episodes.replace_file_bindings(
                task,
                item.id,
                item.name,
                [
                    (key.season, key.episode, metadata[key].id)
                    for key in keys
                ],
                confidence=confidence,
                confirmation="manual",
                segment_index=mapping.segment_index,
            )
        return await self.analyze(task_id)

    async def _task(self, task_id: str) -> TorrentTask:
        task = await self._tasks.get(task_id)
        if task is None:
            raise TorrentNotFoundError("Torrent task not found")
        if task.media_kind != "series":
            raise TorrentFileError("Episode matching is available only for series")
        return task

    async def _regular_seasons(self, task: TorrentTask) -> set[int]:
        try:
            details = await self._catalog.details("series", task.media_id)
        except MetadataError:
            return set()
        return {season.number for season in details.seasons if season.number > 0}

    async def _metadata(
        self,
        task: TorrentTask,
        seasons: set[int],
    ) -> tuple[dict[EpisodeKey, EpisodeSummary], bool]:
        metadata: dict[EpisodeKey, EpisodeSummary] = {}
        available = bool(seasons)
        for season_number in sorted(seasons)[:100]:
            try:
                season = await self._catalog.season(task.media_id, season_number)
            except MetadataError:
                available = False
                continue
            for episode in season.episodes:
                metadata[EpisodeKey(episode.season_number, episode.number)] = episode
        return metadata, available

    def _proposal(
        self,
        item: TorrentFile,
        parsed: ParsedPath,
        metadata: dict[EpisodeKey, EpisodeSummary],
        metadata_available: bool,
    ) -> EpisodeMatchFile:
        if parsed.unsafe:
            return EpisodeMatchFile(
                file_id=item.id,
                file_path=item.name,
                confidence="ambiguous",
                reasons=[parsed.reason],
                unsafe=True,
                duration_seconds=item.duration_seconds,
            )

        if parsed.episodes:
            resolved = [metadata[key] for key in parsed.episodes if key in metadata]
            missing = [key for key in parsed.episodes if key not in metadata]
            identities = [self._identity(episode) for episode in resolved]
            if metadata_available and not missing:
                confidence = "exact" if parsed.explicit else "probable"
                reasons = [
                    "Сезон и серии однозначно указаны в полном пути файла."
                    if parsed.explicit
                    else "Сезон взят из папки, а номер серии — из начала имени файла."
                ]
                if not self._duration_fits(item.duration_seconds, resolved):
                    confidence = "probable"
                    reasons.append("Длительность заметно отличается от метаданных эпизода.")
                return EpisodeMatchFile(
                    file_id=item.id,
                    file_path=item.name,
                    confidence=confidence,
                    episodes=identities,
                    reasons=reasons,
                    duration_seconds=item.duration_seconds,
                )
            return EpisodeMatchFile(
                file_id=item.id,
                file_path=item.name,
                confidence="ambiguous" if missing and metadata_available else "probable",
                episodes=identities or [
                    EpisodeMatchIdentity(
                        season_number=key.season,
                        episode_number=key.episode,
                    )
                    for key in parsed.episodes
                ],
                reasons=[
                    "Не все номера существуют в метаданных TMDB."
                    if missing and metadata_available
                    else "Номера распознаны, но TMDB сейчас недоступен для проверки."
                ],
                duration_seconds=item.duration_seconds,
            )

        season_number = parsed.season_hint
        candidates = [
            episode
            for key, episode in metadata.items()
            if season_number is None or key.season == season_number
        ]
        scored = sorted(
            (
                (self._title_score(item.name, episode.name), episode)
                for episode in candidates
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )
        viable = [(score, episode) for score, episode in scored if score >= 0.48]
        if viable:
            top_score, top = viable[0]
            gap = top_score - (viable[1][0] if len(viable) > 1 else 0)
            if top_score >= 0.72 and gap >= 0.12:
                return EpisodeMatchFile(
                    file_id=item.id,
                    file_path=item.name,
                    confidence="probable",
                    episodes=[self._identity(top)],
                    alternatives=[self._identity(pair[1]) for pair in viable[1:4]],
                    reasons=["Название файла похоже на название эпизода TMDB."],
                    duration_seconds=item.duration_seconds,
                )
            return EpisodeMatchFile(
                file_id=item.id,
                file_path=item.name,
                confidence="ambiguous",
                alternatives=[self._identity(pair[1]) for pair in viable[:4]],
                reasons=["Несколько названий эпизодов подходят с близкой уверенностью."],
                duration_seconds=item.duration_seconds,
            )
        alternatives = [self._identity(episode) for episode in candidates[:20]]
        return EpisodeMatchFile(
            file_id=item.id,
            file_path=item.name,
            confidence="ambiguous",
            alternatives=alternatives,
            reasons=["В пути файла нет однозначного номера или названия эпизода."],
            duration_seconds=item.duration_seconds,
        )

    def _existing_match(
        self,
        item: TorrentFile,
        rows: list[tuple[EpisodeFileBinding, MediaEpisode]],
        metadata: dict[EpisodeKey, EpisodeSummary],
    ) -> EpisodeMatchFile:
        episodes: list[EpisodeMatchIdentity] = []
        confidence: MatchConfidence = "exact"
        confirmation: Literal["automatic", "manual"] = "manual"
        for binding, episode in rows:
            key = EpisodeKey(episode.season_number, episode.episode_number)
            catalog = metadata.get(key)
            episodes.append(
                self._identity(catalog)
                if catalog is not None
                else EpisodeMatchIdentity(
                    season_number=key.season,
                    episode_number=key.episode,
                    catalog_episode_id=episode.catalog_episode_id,
                )
            )
            confidence = cast(MatchConfidence, binding.confidence)
            if binding.confirmation == "automatic":
                confirmation = "automatic"
        return EpisodeMatchFile(
            file_id=item.id,
            file_path=item.name,
            confidence=confidence,
            episodes=sorted(
                episodes,
                key=lambda value: (value.season_number, value.episode_number),
            ),
            reasons=["Использовано сохранённое соответствие для этой раздачи и file_id."],
            confirmed=True,
            confirmation=confirmation,
            duration_seconds=item.duration_seconds,
        )

    @staticmethod
    def _identity(episode: EpisodeSummary) -> EpisodeMatchIdentity:
        return EpisodeMatchIdentity(
            season_number=episode.season_number,
            episode_number=episode.number,
            catalog_episode_id=episode.id,
            name=episode.name,
            runtime_minutes=episode.runtime_minutes,
        )

    @staticmethod
    def _duration_fits(
        duration_seconds: int | None,
        episodes: list[EpisodeSummary],
    ) -> bool:
        runtimes = [episode.runtime_minutes for episode in episodes]
        if duration_seconds is None or any(runtime is None for runtime in runtimes):
            return True
        expected = sum(int(runtime) for runtime in runtimes if runtime is not None) * 60
        return expected * 0.55 <= duration_seconds <= expected * 1.55

    @classmethod
    def _title_score(cls, path: str, title: str) -> float:
        filename = PurePosixPath(path.replace("\\", "/")).stem
        return SequenceMatcher(
            None,
            cls._normalize_title(filename),
            cls._normalize_title(title),
        ).ratio()

    @staticmethod
    def _normalize_title(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value).casefold()
        words = re.findall(r"[a-zа-яё0-9]+", normalized)
        filtered = [
            word
            for word in words
            if word not in _TECHNICAL_WORDS and not re.fullmatch(r"(?:19|20)\d{2}", word)
        ]
        return " ".join(filtered)

    @classmethod
    def parse_path(cls, path: str) -> ParsedPath:
        normalized = path.replace("\\", "/")
        pure = PurePosixPath(normalized)
        if (
            not path
            or pure.is_absolute()
            or re.match(r"^[a-zA-Z]:/", normalized) is not None
            or ".." in pure.parts
            or any(ord(character) < 32 for character in path)
        ):
            return ParsedPath((), None, False, True, "Небезопасный относительный путь файла.")

        patterns = (
            re.compile(
                rf"(?i)(?:^|[^a-z0-9])s(?P<season>\d{{1,3}})\s*e(?P<first>\d{{1,4}})"
                rf"(?P<tail>(?:\s*(?:e|[{_DASHES}])\s*e?\d{{1,4}})*)"
            ),
            re.compile(
                rf"(?i)(?:^|[^0-9])(?P<season>\d{{1,3}})x(?P<first>\d{{1,4}})"
                rf"(?P<tail>(?:\s*(?:x|[{_DASHES}])\s*\d{{1,4}})*)"
            ),
            re.compile(
                rf"(?i)(?:season|сезон)\s*[._ -]*(?P<season>\d{{1,3}})"
                rf"(?:[^a-zа-яё0-9]+)(?:episodes?|сер(?:ия|ии|ий))\s*[._ -]*"
                rf"(?P<first>\d{{1,4}})(?P<tail>(?:\s*(?:episode|ep|серия|[{_DASHES}])\s*\d{{1,4}})*)"
            ),
        )
        for pattern in patterns:
            match = pattern.search(normalized)
            if match:
                episodes = cls._episode_numbers(
                    int(match.group("first")),
                    match.group("tail") or "",
                )
                season = int(match.group("season"))
                if 0 <= season <= 100 and episodes:
                    return ParsedPath(
                        tuple(EpisodeKey(season, number) for number in episodes),
                        season,
                        True,
                        False,
                        "",
                    )

        season_match = re.search(
            r"(?i)(?:^|[/._ -])(?:season|сезон|s)\s*[._ -]*(\d{1,3})(?:[/._ -]|$)",
            normalized,
        )
        season_hint = int(season_match.group(1)) if season_match else None
        if season_hint is not None and not 0 <= season_hint <= 100:
            season_hint = None
        stem = pure.stem
        leading = re.match(r"^\s*(\d{1,4})(?:\s*[._ -]+)", stem)
        if season_hint is not None and leading:
            number = int(leading.group(1))
            if 1 <= number <= 10_000:
                return ParsedPath(
                    (EpisodeKey(season_hint, number),),
                    season_hint,
                    False,
                    False,
                    "",
                )
        return ParsedPath((), season_hint, False, False, "")

    @staticmethod
    def _episode_numbers(first: int, tail: str) -> tuple[int, ...]:
        if not 1 <= first <= 10_000:
            return ()
        tokens = [int(value) for value in re.findall(r"\d{1,4}", tail)]
        if not tokens:
            return (first,)
        last = tokens[-1]
        is_range = any(dash in tail for dash in _DASHES)
        if is_range and last >= first and last - first <= 100:
            return tuple(range(first, last + 1))
        values = (first, *tokens)
        return tuple(dict.fromkeys(value for value in values if 1 <= value <= 10_000))
