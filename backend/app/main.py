from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import httpx
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import SessionFactory, engine
from app.repositories.library import LibraryRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.schemas.system import ErrorResponse
from app.services.cache.exceptions import (
    CacheDeletionConflictError,
    CacheFileNotFoundError,
    CacheStorageError,
)
from app.services.cache.manager import CacheManager
from app.services.library.exceptions import (
    LibraryConflictError,
    LibraryNotFoundError,
    LibraryStorageError,
)
from app.services.metadata.exceptions import (
    MetadataNotConfiguredError,
    MetadataNotFoundError,
    MetadataUnavailableError,
)
from app.services.playback.exceptions import (
    PlaybackArtifactNotReadyError,
    PlaybackPreparationError,
    PlaybackPreparationLimitError,
    PlaybackTrackProbeError,
)
from app.services.playback.manager import CompatibilityManager
from app.services.playback.tracks import PlaybackTrackProbe
from app.services.sources.exceptions import (
    IndexerNotConfiguredError,
    IndexerUnavailableError,
)
from app.services.streaming.exceptions import (
    StreamBufferTimeoutError,
    StreamLimitError,
    StreamNotReadyError,
    StreamRangeError,
)
from app.services.streaming.registry import StreamRegistry
from app.services.torrents.exceptions import (
    TorrentFileError,
    TorrentLimitError,
    TorrentNotConfiguredError,
    TorrentNotFoundError,
    TorrentStorageError,
    TorrentUnavailableError,
)
from app.services.torrents.qbittorrent import QBittorrentClient

settings = get_settings()
logging.basicConfig(
    level=settings.log_level,
    format='{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
)
logger = logging.getLogger(__name__)


async def cache_cleanup_loop(application: FastAPI) -> None:
    interval = settings.cache_cleanup_interval_minutes * 60
    while True:
        await asyncio.sleep(interval)
        try:
            async with SessionFactory() as session:
                manager = CacheManager(
                    TorrentTaskRepository(session),
                    LibraryRepository(session),
                    QBittorrentClient(application.state.torrent_http_client, settings),
                    application.state.stream_registry,
                    application.state.compatibility_manager,
                    settings,
                )
                result = await manager.cleanup()
                if result.removed_tasks:
                    logger.info(
                        "KADR cache cleanup completed: tasks=%s bytes=%s",
                        result.removed_tasks,
                        result.reclaimed_bytes,
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("KADR cache cleanup failed")


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    logger.info("KADR API starting")
    application.state.stream_registry = StreamRegistry(
        settings.max_active_streams,
        settings.max_range_requests_per_stream,
    )
    application.state.compatibility_manager = CompatibilityManager(settings)
    application.state.playback_track_probe = PlaybackTrackProbe(settings)
    async with httpx.AsyncClient(
        base_url=settings.tmdb_base_url,
        timeout=settings.tmdb_timeout_seconds,
        headers={"Accept": "application/json"},
    ) as metadata_http_client:
        async with httpx.AsyncClient(
            base_url=settings.prowlarr_base_url,
            timeout=settings.prowlarr_timeout_seconds,
            headers={"Accept": "application/json"},
        ) as indexer_http_client:
            async with httpx.AsyncClient(
                base_url=settings.qbittorrent_base_url,
                timeout=settings.qbittorrent_timeout_seconds,
                headers={"Accept": "application/json"},
            ) as torrent_http_client:
                application.state.metadata_http_client = metadata_http_client
                application.state.indexer_http_client = indexer_http_client
                application.state.torrent_http_client = torrent_http_client
                cleanup_task = asyncio.create_task(cache_cleanup_loop(application))
                try:
                    yield
                finally:
                    cleanup_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await cleanup_task
                    await application.state.compatibility_manager.close()
    await engine.dispose()
    logger.info("KADR API stopped")


def create_app() -> FastAPI:
    application = FastAPI(
        title="KADR API",
        version="0.1.0",
        description="Backend API for the KADR personal media platform.",
        lifespan=lifespan,
    )
    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
            expose_headers=["Accept-Ranges", "Content-Length", "Content-Range"],
        )
    application.include_router(api_router, prefix="/api/v1")

    @application.exception_handler(MetadataNotConfiguredError)
    async def metadata_not_configured(_: Request, exc: MetadataNotConfiguredError) -> JSONResponse:
        error = ErrorResponse(code="metadata_not_configured", message=str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error.model_dump(),
        )

    @application.exception_handler(MetadataUnavailableError)
    async def metadata_unavailable(_: Request, exc: MetadataUnavailableError) -> JSONResponse:
        error = ErrorResponse(code="metadata_unavailable", message=str(exc))
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=error.model_dump())

    @application.exception_handler(MetadataNotFoundError)
    async def metadata_not_found(_: Request, exc: MetadataNotFoundError) -> JSONResponse:
        error = ErrorResponse(code="media_not_found", message=str(exc))
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=error.model_dump())

    @application.exception_handler(IndexerNotConfiguredError)
    async def indexer_not_configured(
        _: Request,
        exc: IndexerNotConfiguredError,
    ) -> JSONResponse:
        error = ErrorResponse(code="indexer_not_configured", message=str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error.model_dump(),
        )

    @application.exception_handler(IndexerUnavailableError)
    async def indexer_unavailable(_: Request, exc: IndexerUnavailableError) -> JSONResponse:
        error = ErrorResponse(code="indexer_unavailable", message=str(exc))
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=error.model_dump())

    @application.exception_handler(TorrentNotConfiguredError)
    async def torrent_not_configured(_: Request, exc: TorrentNotConfiguredError) -> JSONResponse:
        error = ErrorResponse(code="torrent_not_configured", message=str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=error.model_dump()
        )

    @application.exception_handler(TorrentUnavailableError)
    async def torrent_unavailable(_: Request, exc: TorrentUnavailableError) -> JSONResponse:
        error = ErrorResponse(code="torrent_unavailable", message=str(exc))
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=error.model_dump())

    @application.exception_handler(TorrentNotFoundError)
    async def torrent_not_found(_: Request, exc: TorrentNotFoundError) -> JSONResponse:
        error = ErrorResponse(code="torrent_not_found", message=str(exc))
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=error.model_dump())

    @application.exception_handler(TorrentLimitError)
    async def torrent_limit(_: Request, exc: TorrentLimitError) -> JSONResponse:
        error = ErrorResponse(code="torrent_limit_reached", message=str(exc))
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=error.model_dump())

    @application.exception_handler(TorrentFileError)
    async def torrent_file(_: Request, exc: TorrentFileError) -> JSONResponse:
        error = ErrorResponse(code="invalid_torrent_file", message=str(exc))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error.model_dump()
        )

    @application.exception_handler(TorrentStorageError)
    async def torrent_storage(_: Request, exc: TorrentStorageError) -> JSONResponse:
        error = ErrorResponse(code="torrent_storage_unavailable", message=str(exc))
        return JSONResponse(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE, content=error.model_dump()
        )

    @application.exception_handler(CacheFileNotFoundError)
    async def cache_file_not_found(_: Request, exc: CacheFileNotFoundError) -> JSONResponse:
        error = ErrorResponse(code="cache_file_not_found", message=str(exc))
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=error.model_dump())

    @application.exception_handler(CacheDeletionConflictError)
    async def cache_delete_conflict(
        _: Request,
        exc: CacheDeletionConflictError,
    ) -> JSONResponse:
        error = ErrorResponse(code="cache_delete_conflict", message=str(exc))
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=error.model_dump())

    @application.exception_handler(CacheStorageError)
    async def cache_storage(_: Request, exc: CacheStorageError) -> JSONResponse:
        error = ErrorResponse(code="cache_storage_error", message=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error.model_dump(),
        )

    @application.exception_handler(StreamNotReadyError)
    async def stream_not_ready(_: Request, exc: StreamNotReadyError) -> JSONResponse:
        error = ErrorResponse(code="stream_not_ready", message=str(exc))
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=error.model_dump())

    @application.exception_handler(StreamBufferTimeoutError)
    async def stream_buffer_timeout(
        _: Request, exc: StreamBufferTimeoutError
    ) -> JSONResponse:
        error = ErrorResponse(code="stream_buffer_timeout", message=str(exc))
        return JSONResponse(status_code=status.HTTP_504_GATEWAY_TIMEOUT, content=error.model_dump())

    @application.exception_handler(StreamLimitError)
    async def stream_limit(_: Request, exc: StreamLimitError) -> JSONResponse:
        error = ErrorResponse(code="stream_limit_reached", message=str(exc))
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=error.model_dump(),
        )

    @application.exception_handler(StreamRangeError)
    async def stream_range(_: Request, exc: StreamRangeError) -> JSONResponse:
        error = ErrorResponse(code="range_not_satisfiable", message=str(exc))
        return JSONResponse(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            content=error.model_dump(),
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes */{exc.total_size}",
            },
        )

    @application.exception_handler(PlaybackPreparationError)
    async def playback_preparation(
        _: Request,
        exc: PlaybackPreparationError,
    ) -> JSONResponse:
        error = ErrorResponse(code="playback_preparation_failed", message=str(exc))
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=error.model_dump())

    @application.exception_handler(PlaybackPreparationLimitError)
    async def playback_preparation_limit(
        _: Request,
        exc: PlaybackPreparationLimitError,
    ) -> JSONResponse:
        error = ErrorResponse(code="playback_preparation_limit", message=str(exc))
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=error.model_dump())

    @application.exception_handler(PlaybackArtifactNotReadyError)
    async def playback_artifact_not_ready(
        _: Request,
        exc: PlaybackArtifactNotReadyError,
    ) -> JSONResponse:
        error = ErrorResponse(code="playback_artifact_not_ready", message=str(exc))
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=error.model_dump())

    @application.exception_handler(PlaybackTrackProbeError)
    async def playback_track_probe(
        _: Request,
        exc: PlaybackTrackProbeError,
    ) -> JSONResponse:
        error = ErrorResponse(code="playback_tracks_unavailable", message=str(exc))
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=error.model_dump())

    @application.exception_handler(LibraryNotFoundError)
    async def library_not_found(_: Request, exc: LibraryNotFoundError) -> JSONResponse:
        error = ErrorResponse(code="library_not_found", message=str(exc))
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=error.model_dump())

    @application.exception_handler(LibraryConflictError)
    async def library_conflict(_: Request, exc: LibraryConflictError) -> JSONResponse:
        error = ErrorResponse(code="library_conflict", message=str(exc))
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=error.model_dump())

    @application.exception_handler(LibraryStorageError)
    async def library_storage(_: Request, exc: LibraryStorageError) -> JSONResponse:
        error = ErrorResponse(code="library_storage", message=str(exc))
        return JSONResponse(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            content=error.model_dump(),
        )

    return application


app = create_app()
