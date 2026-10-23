from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def test_health_reports_api_and_database_ready(client: AsyncClient) -> None:
    response = await client.get("/api/v1/system/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "kadr-api",
        "version": "0.1.0",
        "database": "ok",
    }


async def test_sqlite_foreign_keys_and_wal_are_enabled(session: AsyncSession) -> None:
    foreign_keys = (await session.execute(text("PRAGMA foreign_keys"))).scalar_one()
    journal_mode = (await session.execute(text("PRAGMA journal_mode"))).scalar_one()

    assert foreign_keys == 1
    assert journal_mode == "wal"

