from typing import Annotated

from fastapi import APIRouter, Header, Query, Request, status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.api.dependencies import (
    EpisodeNavigationServiceDependency,
    PlaybackPreparationServiceDependency,
    PlaybackResolverDependency,
)
from app.schemas.playback import (
    NextEpisodeRequest,
    NextEpisodeResolution,
    PlaybackMode,
    PlaybackPreparation,
    PlaybackResolution,
    PlaybackResolveRequest,
)

router = APIRouter()


@router.post("/playback/resolve", response_model=PlaybackResolution)
async def resolve_playback(
    body: PlaybackResolveRequest,
    resolver: PlaybackResolverDependency,
) -> PlaybackResolution:
    return await resolver.resolve(body)


@router.post("/playback/next", response_model=NextEpisodeResolution)
async def resolve_next_episode(
    body: NextEpisodeRequest,
    service: EpisodeNavigationServiceDependency,
) -> NextEpisodeResolution:
    return await service.resolve_next(body)


@router.post("/playback/next/prefetch", response_model=NextEpisodeResolution)
async def prefetch_next_episode(
    body: NextEpisodeRequest,
    service: EpisodeNavigationServiceDependency,
) -> NextEpisodeResolution:
    return await service.prefetch_next(body)


@router.post(
    "/torrents/{task_id}/compatible",
    response_model=PlaybackPreparation,
    status_code=status.HTTP_202_ACCEPTED,
)
async def prepare_compatible_playback(
    service: PlaybackPreparationServiceDependency,
    task_id: str,
    mode: Annotated[PlaybackMode, Query()] = "compatible",
) -> PlaybackPreparation:
    return await service.prepare(task_id, mode)


@router.get(
    "/torrents/{task_id}/compatible",
    response_model=PlaybackPreparation,
)
async def compatible_playback_status(
    service: PlaybackPreparationServiceDependency,
    task_id: str,
    mode: Annotated[PlaybackMode, Query()] = "compatible",
) -> PlaybackPreparation:
    return await service.status(task_id, mode)


@router.get(
    "/torrents/{task_id}/compatible/stream",
    response_class=StreamingResponse,
)
async def stream_compatible_playback(
    request: Request,
    service: PlaybackPreparationServiceDependency,
    task_id: str,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
    mode: Annotated[PlaybackMode, Query()] = "compatible",
) -> StreamingResponse:
    prepared = await service.open(
        task_id,
        mode,
        range_header,
        request.app.state.stream_registry,
    )
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(prepared.byte_range.length),
        "Cache-Control": "no-store",
    }
    response_status = status.HTTP_200_OK
    if prepared.byte_range.partial:
        response_status = status.HTTP_206_PARTIAL_CONTENT
        headers["Content-Range"] = (
            f"bytes {prepared.byte_range.start}-{prepared.byte_range.end}/"
            f"{prepared.byte_range.total}"
        )
    return StreamingResponse(
        prepared.content,
        status_code=response_status,
        media_type=prepared.media_type,
        headers=headers,
        background=BackgroundTask(prepared.release),
    )
