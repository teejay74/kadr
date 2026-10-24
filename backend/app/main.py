from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import engine
from app.schemas.system import ErrorResponse
from app.services.metadata.exceptions import (
    MetadataNotConfiguredError,
    MetadataNotFoundError,
    MetadataUnavailableError,
)
from app.services.sources.exceptions import (
    IndexerNotConfiguredError,
    IndexerUnavailableError,
)

settings = get_settings()
logging.basicConfig(
    level=settings.log_level,
    format='{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    logger.info("KADR API starting")
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
            application.state.metadata_http_client = metadata_http_client
            application.state.indexer_http_client = indexer_http_client
            yield
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

    return application


app = create_app()

