from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Path, Query
from fastapi.responses import FileResponse

from app.api.dependencies import (
    CacheManagerDependency,
    EpisodeMatcherDependency,
    PlaybackTrackServiceDependency,
    TorrentManagerDependency,
)
from app.schemas.episode_matcher import (
    EpisodeMatchConfirmationRequest,
    EpisodeMatchReport,
)
from app.schemas.library import CacheFileDeletionResponse, CacheTaskDeletionResponse
from app.schemas.media import MediaKind
from app.schemas.playback import (
    PlaybackSubtitlePreparation,
    PlaybackTrackList,
    PlaybackTrackPreferenceRequest,
)
from app.schemas.torrents import (
    AddTorrentRequest,
    EpisodeFileBindingResponse,
    PrefetchTorrentFilesRequest,
    SelectTorrentFileRequest,
    TorrentFile,
    TorrentStatus,
)

router = APIRouter()


@router.get("/torrents", response_model=list[TorrentStatus])
async def list_torrents(manager: TorrentManagerDependency) -> list[TorrentStatus]:
    return await manager.list_tasks()


@router.post("/media/{media_id}/torrents", response_model=TorrentStatus, status_code=201)
async def add_torrent(
    manager: TorrentManagerDependency,
    body: AddTorrentRequest,
    media_id: Annotated[int, Path(gt=0)],
) -> TorrentStatus:
    return await manager.add(
        media_id,
        body.media_kind,
        body.source_id,
        body.season_number,
    )


@router.get("/media/{media_id}/torrents", response_model=TorrentStatus)
async def current_torrent(
    manager: TorrentManagerDependency,
    media_id: Annotated[int, Path(gt=0)],
    media_kind: Annotated[MediaKind, Query()],
) -> TorrentStatus:
    return await manager.current(media_id, media_kind)


@router.get("/torrents/{task_id}", response_model=TorrentStatus)
async def torrent_status(
    manager: TorrentManagerDependency,
    task_id: str,
) -> TorrentStatus:
    return await manager.status(task_id)


@router.get("/torrents/{task_id}/files", response_model=list[TorrentFile])
async def torrent_files(
    manager: TorrentManagerDependency,
    task_id: str,
) -> list[TorrentFile]:
    return await manager.files(task_id)


@router.get("/torrents/{task_id}/tracks", response_model=PlaybackTrackList)
async def torrent_tracks(
    service: PlaybackTrackServiceDependency,
    task_id: str,
    profile_key: Annotated[str, Query(min_length=1, max_length=64)] = "default",
) -> PlaybackTrackList:
    return await service.torrent_tracks(task_id, profile_key)


@router.put("/torrents/{task_id}/tracks/preferences", response_model=PlaybackTrackList)
async def save_torrent_track_preferences(
    service: PlaybackTrackServiceDependency,
    task_id: str,
    body: PlaybackTrackPreferenceRequest,
) -> PlaybackTrackList:
    return await service.save_torrent_preferences(task_id, body)


@router.post(
    "/torrents/{task_id}/tracks/{track_id}/subtitle",
    response_model=PlaybackSubtitlePreparation,
)
async def prepare_torrent_subtitle(
    service: PlaybackTrackServiceDependency,
    task_id: str,
    track_id: str,
) -> PlaybackSubtitlePreparation:
    artifact = await service.prepare_torrent_subtitle(task_id, track_id)
    task = quote(task_id, safe="")
    return PlaybackSubtitlePreparation(
        track_id=track_id,
        stream_url=f"/api/v1/torrents/{task}/subtitles/{artifact.artifact_id}.vtt",
    )


@router.get("/torrents/{task_id}/subtitles/{artifact_id}.vtt")
async def stream_torrent_subtitle(
    service: PlaybackTrackServiceDependency,
    task_id: str,
    artifact_id: str,
) -> FileResponse:
    path = await service.open_torrent_subtitle(task_id, artifact_id)
    return FileResponse(path, media_type="text/vtt", filename="subtitles.vtt")


@router.get(
    "/torrents/{task_id}/episode-files",
    response_model=list[EpisodeFileBindingResponse],
)
async def torrent_episode_files(
    manager: TorrentManagerDependency,
    task_id: str,
) -> list[EpisodeFileBindingResponse]:
    return await manager.episode_files(task_id)


@router.post(
    "/torrents/{task_id}/episode-matches/analyze",
    response_model=EpisodeMatchReport,
)
async def analyze_episode_matches(
    matcher: EpisodeMatcherDependency,
    task_id: str,
) -> EpisodeMatchReport:
    return await matcher.analyze(task_id)


@router.put(
    "/torrents/{task_id}/episode-matches",
    response_model=EpisodeMatchReport,
)
async def confirm_episode_matches(
    matcher: EpisodeMatcherDependency,
    task_id: str,
    body: EpisodeMatchConfirmationRequest,
) -> EpisodeMatchReport:
    return await matcher.confirm(task_id, body)


@router.delete(
    "/torrents/{task_id}/files/{file_id}",
    response_model=CacheFileDeletionResponse,
)
async def delete_torrent_file(
    manager: CacheManagerDependency,
    task_id: str,
    file_id: Annotated[int, Path(ge=0)],
) -> CacheFileDeletionResponse:
    return await manager.delete_file(task_id, file_id)


@router.delete(
    "/torrents/{task_id}",
    response_model=CacheTaskDeletionResponse,
)
async def delete_torrent_task(
    manager: CacheManagerDependency,
    task_id: str,
) -> CacheTaskDeletionResponse:
    return await manager.delete_task(task_id)


@router.put("/torrents/{task_id}/selection", response_model=TorrentStatus)
async def select_torrent_file(
    manager: TorrentManagerDependency,
    task_id: str,
    body: SelectTorrentFileRequest,
) -> TorrentStatus:
    return await manager.select_file(
        task_id,
        body.file_id,
        body.season_number,
        body.episode_number,
        body.catalog_episode_id,
        body.variant_label,
    )


@router.put("/torrents/{task_id}/prefetch", response_model=TorrentStatus)
async def prefetch_torrent_files(
    manager: TorrentManagerDependency,
    task_id: str,
    body: PrefetchTorrentFilesRequest,
) -> TorrentStatus:
    return await manager.configure_prefetch(task_id, body.file_ids)


@router.post("/torrents/{task_id}/start", response_model=TorrentStatus)
async def start_torrent(manager: TorrentManagerDependency, task_id: str) -> TorrentStatus:
    return await manager.start(task_id)


@router.post("/torrents/{task_id}/stop", response_model=TorrentStatus)
async def stop_torrent(manager: TorrentManagerDependency, task_id: str) -> TorrentStatus:
    return await manager.stop(task_id)
