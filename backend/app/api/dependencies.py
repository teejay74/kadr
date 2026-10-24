from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.repositories.metadata_cache import MetadataCacheRepository
from app.services.metadata.catalog import CatalogService
from app.services.metadata.tmdb import TMDBClient
from app.services.sources.prowlarr import ProwlarrClient
from app.services.sources.search import SourceSearchService


def get_catalog_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CatalogService:
    settings = get_settings()
    return CatalogService(
        TMDBClient(request.app.state.metadata_http_client, settings),
        MetadataCacheRepository(session),
        settings,
    )


CatalogServiceDependency = Annotated[CatalogService, Depends(get_catalog_service)]


def get_source_search_service(
    request: Request,
    catalog: CatalogServiceDependency,
) -> SourceSearchService:
    settings = get_settings()
    return SourceSearchService(
        catalog,
        ProwlarrClient(request.app.state.indexer_http_client, settings),
    )


SourceSearchServiceDependency = Annotated[
    SourceSearchService,
    Depends(get_source_search_service),
]
