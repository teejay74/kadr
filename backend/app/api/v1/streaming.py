from typing import Annotated

from fastapi import APIRouter, Header, status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.api.dependencies import StreamingManagerDependency
from app.schemas.torrents import StreamReadiness

router = APIRouter()


@router.get("/torrents/{task_id}/stream/readiness", response_model=StreamReadiness)
async def stream_readiness(
    manager: StreamingManagerDependency,
    task_id: str,
) -> StreamReadiness:
    return await manager.readiness(task_id)


@router.get("/torrents/{task_id}/stream", response_class=StreamingResponse)
async def stream_torrent_file(
    manager: StreamingManagerDependency,
    task_id: str,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> StreamingResponse:
    prepared = await manager.open(task_id, range_header)
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
