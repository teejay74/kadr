from typing import Annotated

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.api.dependencies import (
    CompatibilityManagerDependency,
    PlaybackPreparationServiceDependency,
)
from app.schemas.playback import PlaybackPreparation

router = APIRouter()


@router.post(
    "/torrents/{task_id}/compatible",
    response_model=PlaybackPreparation,
    status_code=status.HTTP_202_ACCEPTED,
)
async def prepare_compatible_playback(
    service: PlaybackPreparationServiceDependency,
    task_id: str,
) -> PlaybackPreparation:
    return await service.prepare(task_id)


@router.get(
    "/torrents/{task_id}/compatible",
    response_model=PlaybackPreparation,
)
async def compatible_playback_status(
    manager: CompatibilityManagerDependency,
    task_id: str,
) -> PlaybackPreparation:
    return manager.status(task_id)


@router.get(
    "/torrents/{task_id}/compatible/stream",
    response_class=StreamingResponse,
)
async def stream_compatible_playback(
    request: Request,
    manager: CompatibilityManagerDependency,
    task_id: str,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> StreamingResponse:
    prepared = await manager.open(
        task_id,
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
