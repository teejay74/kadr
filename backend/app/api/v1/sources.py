from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.dependencies import SourceSearchServiceDependency
from app.schemas.media import MediaKind
from app.schemas.sources import IndexerSummary, SortOrder, SourceResults, SourceSort

router = APIRouter()


@router.get("/media/{media_id}/sources", response_model=SourceResults)
async def media_sources(
    service: SourceSearchServiceDependency,
    media_id: Annotated[int, Path(gt=0)],
    kind: Annotated[MediaKind, Query()],
    sort: SourceSort = "seeders",
    order: SortOrder = "desc",
    season_number: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> SourceResults:
    return await service.search(media_id, kind, sort, order, season_number)


@router.get("/indexers", response_model=list[IndexerSummary])
async def indexers(service: SourceSearchServiceDependency) -> list[IndexerSummary]:
    return await service.indexers()
