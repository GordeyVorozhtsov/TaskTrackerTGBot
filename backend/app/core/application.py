import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from sqlalchemy.exc import SQLAlchemyError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.auth import TelegramAuth
from app.bot.runner import TelegramBot
from app.core.config import Settings
from app.core.errors import format_validation_error, user_facing_error
from app.core.startup_validation import validate_settings
from app.infra.database import Database
from app.infra.logger import AppLogging
from app.infra.logging_middleware import RequestLoggingMiddleware
from app.infra.migrations import MigrationRunner
from app.infra.rate_limit import RateLimiter
from app.infra.static_files import NoCacheStaticFiles
from app.infra.storage import Storage
from app.infra.upload_signing import UploadSigning

SHUTDOWN_TIMEOUT_SEC = 5.0


class Application:
    def __init__(self) -> None:
        self.settings = Settings()
        self.logging = AppLogging(self.settings)
        self.logging.configure()
        validate_settings(self.settings)

        self.db = Database(self.settings)
        self.storage = Storage(self.settings, self.logging.get_logger("storage"))
        self.upload_signing = UploadSigning(self.settings)
        self.rate_limiter = RateLimiter(self.settings)
        self.auth = TelegramAuth(self.settings, self.logging.get_logger("auth"))
        self.bot = TelegramBot(self.settings, self.logging.get_logger("bot"))
        self.migrations = MigrationRunner(
            self.settings,
            self.db,
            self.logging.get_logger("migrations"),
        )
        self.logger = self.logging.get_logger("application")

    def get_logger(self, name: str) -> logging.Logger:
        return self.logging.get_logger(name)

    async def _shutdown_bot(self, bot_task: asyncio.Task | None) -> None:
        if bot_task is None:
            return

        await self.bot.stop()
        bot_task.cancel()
        try:
            await asyncio.wait_for(bot_task, timeout=SHUTDOWN_TIMEOUT_SEC)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    def create_app(self) -> FastAPI:
        from app.api.routes import create_api_router

        settings = self.settings
        logger = self.logger

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            logger.info(
                "Application starting | debug=%s env=%s db_pool=%s+%s recycle=%ss",
                settings.debug,
                settings.environment,
                settings.db_pool_size,
                settings.db_max_overflow,
                settings.db_pool_recycle,
            )
            await self.migrations.run()
            self.storage.uploads_dir()

            bot_task = None
            if settings.has_bot:
                bot_task = asyncio.create_task(self.bot.run(), name="telegram-bot")
                logger.info("Telegram bot task created")

            try:
                yield
            finally:
                logger.info("Application shutting down...")
                await self._shutdown_bot(bot_task)
                await self.db.close()
                logger.info("Database pool disposed")
                logger.info("Application stopped")

        app = FastAPI(
            title=settings.app_name,
            lifespan=lifespan,
            docs_url="/docs" if settings.debug else None,
            redoc_url="/redoc" if settings.debug else None,
            openapi_url="/openapi.json" if settings.debug else None,
        )

        app.state.application = self
        app.state.limiter = self.rate_limiter.limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIMiddleware)

        self._register_exception_handlers(app)

        app.add_middleware(RequestLoggingMiddleware)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        app.include_router(create_api_router(self))

        frontend_dir = settings.frontend_dir
        if frontend_dir.exists():
            app.mount(
                "/",
                NoCacheStaticFiles(directory=str(frontend_dir), html=True),
                name="frontend",
            )

        return app

    def _register_exception_handlers(self, app: FastAPI) -> None:
        api_logger = self.get_logger("api")

        @app.exception_handler(HTTPException)
        async def http_exception_handler(
            request: Request, exc: HTTPException
        ) -> JSONResponse:
            if exc.status_code >= 500:
                api_logger.error(
                    "HTTPException %s %s -> %s | detail=%s",
                    request.method,
                    request.url.path,
                    exc.status_code,
                    exc.detail,
                )
            else:
                api_logger.warning(
                    "HTTPException %s %s -> %s | detail=%s",
                    request.method,
                    request.url.path,
                    exc.status_code,
                    exc.detail,
                )
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        @app.exception_handler(RequestValidationError)
        async def validation_exception_handler(
            request: Request, exc: RequestValidationError
        ) -> JSONResponse:
            message = format_validation_error(exc)
            api_logger.warning(
                "Ошибка валидации %s %s | %s | errors=%s",
                request.method,
                request.url.path,
                message,
                exc.errors(),
            )
            return JSONResponse(status_code=422, content={"detail": message})

        @app.exception_handler(ResponseValidationError)
        async def response_validation_exception_handler(
            request: Request, exc: ResponseValidationError
        ) -> JSONResponse:
            api_logger.error(
                "Ошибка формирования ответа %s %s | %s: %s | errors=%s",
                request.method,
                request.url.path,
                type(exc).__name__,
                exc,
                exc.errors(),
            )
            detail = (
                str(exc)
                if settings.debug
                else "Сервер не смог сформировать ответ. Попробуйте позже."
            )
            return JSONResponse(status_code=500, content={"detail": detail})

        @app.exception_handler(SQLAlchemyError)
        async def sqlalchemy_exception_handler(
            request: Request, exc: SQLAlchemyError
        ) -> JSONResponse:
            api_logger.exception(
                "Ошибка базы данных %s %s | %s: %s",
                request.method,
                request.url.path,
                type(exc).__name__,
                exc,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": user_facing_error(exc, debug=settings.debug)},
            )

        @app.exception_handler(Exception)
        async def unhandled_exception_handler(
            request: Request, exc: Exception
        ) -> JSONResponse:
            api_logger.exception(
                "Необработанная ошибка %s %s | %s: %s",
                request.method,
                request.url.path,
                type(exc).__name__,
                exc,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": user_facing_error(exc, debug=settings.debug)},
            )
