import logging
import os
from logging.handlers import RotatingFileHandler

from app.core.config import Settings

_ROOT_LOGGER_NAME = "app"
_LOG_FORMAT = "%(levelname)s - %(name)s - %(asctime)s - %(message)s"


class AppLogging:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._configured = False

    def _resolve_level(self) -> int:
        level_name = os.getenv("PYTEST_LOG_LEVEL") or os.getenv("LOG_LEVEL")
        if not level_name:
            level_name = "DEBUG" if self.settings.debug else "INFO"
        return getattr(logging, level_name.upper(), logging.INFO)

    def configure(self) -> None:
        if self._configured:
            return

        self.settings.log_dir.mkdir(parents=True, exist_ok=True)
        level = self._resolve_level()
        formatter = logging.Formatter(_LOG_FORMAT)

        root = logging.getLogger(_ROOT_LOGGER_NAME)
        root.setLevel(level)
        root.handlers.clear()

        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(formatter)
        root.addHandler(console)

        log_path = self.settings.log_dir / self.settings.log_file
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=self.settings.log_max_bytes,
            backupCount=self.settings.log_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

        root.propagate = False
        self._configured = True

        root.info(
            "Logging initialized | file=%s | level=%s | max_bytes=%s | backups=%s",
            log_path,
            logging.getLevelName(level),
            self.settings.log_max_bytes,
            self.settings.log_backup_count,
        )

    def get_logger(self, name: str = "application") -> logging.Logger:
        self.configure()
        if name.startswith(f"{_ROOT_LOGGER_NAME}."):
            return logging.getLogger(name)
        if name == _ROOT_LOGGER_NAME:
            return logging.getLogger(_ROOT_LOGGER_NAME)
        return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")


def log_action(
    logger: logging.Logger,
    action: str,
    *,
    user_id: int | None = None,
    level: int = logging.INFO,
    **fields,
) -> None:
    parts = [f"action={action}"]
    if user_id is not None:
        parts.append(f"user_id={user_id}")
    for key, value in fields.items():
        if value is not None:
            parts.append(f"{key}={value}")
    logger.log(level, " | ".join(parts))
