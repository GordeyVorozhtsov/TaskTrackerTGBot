from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import Database


def create_db_dependency(database: Database):
    async def get_db() -> AsyncGenerator[AsyncSession, None]:
        async for session in database.get_session():
            yield session

    return get_db
