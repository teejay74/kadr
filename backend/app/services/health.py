import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.system import HealthResponse

logger = logging.getLogger(__name__)


class HealthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def check(self) -> HealthResponse:
        try:
            await self._session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.exception("Database health check failed")
            return HealthResponse(status="degraded", database="unavailable")
        return HealthResponse(status="ok", database="ok")

