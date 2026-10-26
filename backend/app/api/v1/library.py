from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Header, Path, Query, Response, status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.api.dependencies import CacheManagerDependency, LibraryManagerDependency
from app.schemas.library import (
    CacheCleanupResponse,
    FavoriteRequest,
    FavoriteResponse,
    HistoryResponse,
    HistoryUpdateRequest,
    LibraryItemResponse,
    SaveLibraryItemRequest,
    StorageResponse,
)
from app.schemas.media import MediaKind

router = APIRouter()


@router.get("/library", response_model=list[LibraryItemResponse])
async def list_library(manager: LibraryManagerDependency) -> list[LibraryItemResponse]:
    return await manager.list()


@router.post("/library", response_model=LibraryItemResponse, status_code=201)
async def save_library_item(
    body: SaveLibraryItemRequest,
    manager: LibraryManagerDependency,
) -> LibraryItemResponse:
    return await manager.save(body)


@router.delete("/library/{item_id}", status_code=204)
async def delete_library_item(manager: LibraryManagerDependency, item_id: str) -> Response:
    await manager.delete(item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/library/{item_id}/stream")
async def stream_library_item(
    manager: LibraryManagerDependency,
    item_id: str,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> StreamingResponse:
    prepared = await manager.open(item_id, range_header)
    byte_range = prepared.byte_range
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(byte_range.length),
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(prepared.filename)}",
    }
    response_status = status.HTTP_200_OK
    if range_header is not None:
        response_status = status.HTTP_206_PARTIAL_CONTENT
        headers["Content-Range"] = (
            f"bytes {byte_range.start}-{byte_range.end}/{byte_range.total}"
        )
    return StreamingResponse(
        prepared.content,
        status_code=response_status,
        media_type=prepared.media_type,
        headers=headers,
        background=BackgroundTask(prepared.release),
    )


@router.get("/favorites", response_model=list[FavoriteResponse])
async def list_favorites(manager: LibraryManagerDependency) -> list[FavoriteResponse]:
    return await manager.list_favorites()


@router.post("/favorites", response_model=FavoriteResponse, status_code=201)
async def add_favorite(
    body: FavoriteRequest,
    manager: LibraryManagerDependency,
) -> FavoriteResponse:
    return await manager.favorite(body)


@router.delete("/favorites/{media_kind}/{media_id}", status_code=204)
async def remove_favorite(
    manager: LibraryManagerDependency,
    media_kind: MediaKind,
    media_id: Annotated[int, Path(gt=0)],
) -> Response:
    await manager.remove_favorite(media_id, media_kind)
    return Response(status_code=204)


@router.get("/history", response_model=list[HistoryResponse])
async def list_history(manager: LibraryManagerDependency) -> list[HistoryResponse]:
    return await manager.list_history()


@router.get("/history/{media_id}", response_model=HistoryResponse | None)
async def get_history(
    manager: LibraryManagerDependency,
    media_id: Annotated[int, Path(gt=0)],
    media_kind: Annotated[MediaKind, Query()],
) -> HistoryResponse | None:
    return await manager.get_history(media_id, media_kind)


@router.put("/history/{media_id}", response_model=HistoryResponse)
async def update_history(
    body: HistoryUpdateRequest,
    manager: LibraryManagerDependency,
    media_id: Annotated[int, Path(gt=0)],
) -> HistoryResponse:
    return await manager.history(media_id, body)


@router.post("/cache/cleanup", response_model=CacheCleanupResponse)
async def cleanup_cache(manager: CacheManagerDependency) -> CacheCleanupResponse:
    return await manager.cleanup()


@router.get("/system/storage", response_model=StorageResponse)
async def storage_status(manager: CacheManagerDependency) -> StorageResponse:
    return await manager.storage()
