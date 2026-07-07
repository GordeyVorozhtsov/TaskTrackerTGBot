"""Run Alembic migrations on application startup."""

from __future__ import annotations

import asyncio
import logging

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.core.paths import BACKEND_DIR
from app.infra.database import Database

ALEMBIC_INI = BACKEND_DIR / "alembic.ini"

_SCHEMA_TABLES = ("users", "boards", "board_members", "tasks", "task_comments")

# MySQL connection / availability errors — safe to retry.
_TRANSIENT_MYSQL_CODES = frozenset({1040, 1042, 2002, 2003, 2006, 2013})


def _is_connection_error(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionRefusedError, ConnectionResetError, TimeoutError)):
        return True
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in (61, 111):
        return True

    checked: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in checked:
        checked.append(current)
        if isinstance(current, OperationalError):
            orig = current.orig
            if orig is not None:
                args = getattr(orig, "args", ())
                if args and args[0] in _TRANSIENT_MYSQL_CODES:
                    return True
        current = current.__cause__ or current.__context__

    return False


class MigrationRunner:
    def __init__(
        self, settings: Settings, database: Database, logger: logging.Logger
    ) -> None:
        self.settings = settings
        self.database = database
        self.logger = logger

    def _alembic_config(self) -> Config:
        cfg = Config(str(ALEMBIC_INI))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        cfg.set_main_option("prepend_sys_path", str(BACKEND_DIR))
        cfg.set_main_option("sqlalchemy.url", self.settings.sync_database_url)
        return cfg

    def _upgrade_head(self) -> None:
        command.upgrade(self._alembic_config(), "head")

    def _stamp_revision(self, revision: str) -> None:
        command.stamp(self._alembic_config(), revision)

    async def _table_exists(self, name: str) -> bool:
        async with self.database.engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT EXISTS ("
                    "  SELECT 1 FROM information_schema.tables "
                    "  WHERE table_schema = DATABASE() AND table_name = :name"
                    ")"
                ),
                {"name": name},
            )
            return bool(result.scalar())

    async def _schema_ready(self) -> bool:
        for name in _SCHEMA_TABLES:
            if not await self._table_exists(name):
                return False
        return True

    async def _prepare_existing_schema(self) -> None:
        has_alembic = await self._table_exists("alembic_version")
        if has_alembic:
            return

        if await self._schema_ready():
            self.logger.info("Existing schema without alembic_version — stamping 001")
            await asyncio.to_thread(self._stamp_revision, "001")
            return

        if await self._table_exists("users"):
            raise RuntimeError(
                "Database schema is incomplete (partial migration from a previous run).\n"
                "Reset local database:\n"
                "  make down-v && make db"
            )

    async def run(self, retries: int = 30, delay: float = 1.0) -> None:
        last_error: Exception | None = None

        for attempt in range(1, retries + 1):
            try:
                await self.database.ping()
                await self._prepare_existing_schema()
                await asyncio.to_thread(self._upgrade_head)
                self.logger.info("Database migrations applied")
                return
            except Exception as exc:
                if not _is_connection_error(exc):
                    raise RuntimeError(f"Database migration failed: {exc}") from exc

                last_error = exc
                if attempt < retries:
                    self.logger.warning(
                        "MySQL not ready (attempt %s/%s), retrying in %ss...",
                        attempt,
                        retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    break

        raise RuntimeError(
            "Cannot connect to MySQL. Start the database first:\n"
            "  make db"
        ) from last_error
