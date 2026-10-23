from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.system import ErrorResponse, HealthResponse
from app.services.health import HealthService

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": ErrorResponse}},
)
async def health(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HealthResponse | JSONResponse:
    result = await HealthService(session).check()
    if result.status == "ok":
        return result
    error = ErrorResponse(code="service_unavailable", message="Database is unavailable")
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=error.model_dump())

