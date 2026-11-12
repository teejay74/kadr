from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query

from app.api.dependencies import CatalogServiceDependency
from app.schemas.media import Genre, MediaDetails, MediaPage, SeasonDetails
from app.services.metadata.catalog import AgeRating

router = APIRouter()
Page = Annotated[int, Query(ge=1, le=500)]
Year = Annotated[int | None, Query(ge=1870, le=2100)]
FallbackTitle = Annotated[str | None, Query(min_length=2, max_length=200)]
Sort = Literal["popular", "rating", "newest"]


@router.get("/movies", response_model=MediaPage)
async def movies(
    service: CatalogServiceDependency,
    page: Page = 1,
    sort: Sort = "popular",
    genre: Annotated[int | None, Query(gt=0)] = None,
    year: Year = None,
    age_rating: AgeRating | None = None,
    released_within_days: Annotated[int | None, Query(ge=1, le=730)] = None,
) -> MediaPage:
    return await service.list_media(
        "movie",
        page=page,
        sort=sort,
        genre=genre,
        year=year,
        age_rating=age_rating,
        released_within_days=released_within_days,
    )


@router.get("/movies/search", response_model=MediaPage)
async def search_movies(
    service: CatalogServiceDependency,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    page: Page = 1,
    year: Year = None,
) -> MediaPage:
    return await service.search("movie", q.strip(), page=page, year=year)


@router.get("/movies/genres", response_model=list[Genre])
async def movie_genres(service: CatalogServiceDependency) -> list[Genre]:
    return await service.genres("movie")


@router.get("/movies/{media_id}", response_model=MediaDetails)
async def movie_details(
    service: CatalogServiceDependency,
    media_id: Annotated[int, Path(gt=0)],
    fallback_title: FallbackTitle = None,
    fallback_year: Year = None,
) -> MediaDetails:
    return await service.details(
        "movie",
        media_id,
        fallback_title=fallback_title.strip() if fallback_title else None,
        fallback_year=fallback_year,
        include_ratings=True,
        allow_partial=True,
    )


@router.get("/series", response_model=MediaPage)
async def series(
    service: CatalogServiceDependency,
    page: Page = 1,
    sort: Sort = "popular",
    genre: Annotated[int | None, Query(gt=0)] = None,
    year: Year = None,
    released_within_days: Annotated[int | None, Query(ge=1, le=730)] = None,
) -> MediaPage:
    return await service.list_media(
        "series",
        page=page,
        sort=sort,
        genre=genre,
        year=year,
        released_within_days=released_within_days,
    )


@router.get("/series/search", response_model=MediaPage)
async def search_series(
    service: CatalogServiceDependency,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    page: Page = 1,
    year: Year = None,
) -> MediaPage:
    return await service.search("series", q.strip(), page=page, year=year)


@router.get("/series/genres", response_model=list[Genre])
async def series_genres(service: CatalogServiceDependency) -> list[Genre]:
    return await service.genres("series")


@router.get(
    "/series/{media_id}/seasons/{season_number}",
    response_model=SeasonDetails,
)
async def series_season(
    service: CatalogServiceDependency,
    media_id: Annotated[int, Path(gt=0)],
    season_number: Annotated[int, Path(ge=0, le=100)],
) -> SeasonDetails:
    return await service.season(media_id, season_number)


@router.get("/series/{media_id}", response_model=MediaDetails)
async def series_details(
    service: CatalogServiceDependency,
    media_id: Annotated[int, Path(gt=0)],
    fallback_title: FallbackTitle = None,
    fallback_year: Year = None,
) -> MediaDetails:
    return await service.details(
        "series",
        media_id,
        fallback_title=fallback_title.strip() if fallback_title else None,
        fallback_year=fallback_year,
        allow_partial=True,
    )
