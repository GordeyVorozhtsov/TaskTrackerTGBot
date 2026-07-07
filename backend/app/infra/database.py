from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings


class Base(DeclarativeBase):
    pass


def engine_options(settings: Settings) -> dict[str, Any]:
    """Shared SQLAlchemy engine kwargs for runtime and Alembic (aiomysql)."""
    return {
        "echo": False,
        "pool_pre_ping": True,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout,
        "pool_recycle": settings.db_pool_recycle,
        "connect_args": {
            "connect_timeout": settings.db_connect_timeout,
        },
    }


def sync_engine_options(settings: Settings) -> dict[str, Any]:
    """PyMySQL connect kwargs for sync tools (Alembic CLI offline / startup migrations)."""
    return {
        "connect_args": {
            "connect_timeout": settings.db_connect_timeout,
            "read_timeout": settings.db_read_timeout,
            "write_timeout": settings.db_write_timeout,
        },
    }


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(settings.async_database_url, **engine_options(settings))


async def flush_and_refresh(session: AsyncSession, instance: object) -> None:
    """Persist changes and load server-generated columns (MySQL has no RETURNING)."""
    await session.flush()
    await session.refresh(instance)


class Database:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.engine = create_engine(settings)
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def ping(self) -> None:
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self.engine.dispose()

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
