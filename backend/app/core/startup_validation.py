import logging
from urllib.parse import unquote, urlparse

from app.core.config import Settings

logger = logging.getLogger("app.startup")

WEAK_DB_PASSWORD = "tasktracker"


def _database_password(settings: Settings) -> str:
    if settings.database_url:
        url = settings.database_url.replace("mysql+aiomysql://", "mysql://")
        parsed = urlparse(url)
        return unquote(parsed.password or "")
    return settings.mysql_password


def validate_settings(settings: Settings) -> None:
    if not settings.is_production:
        return

    if settings.debug:
        raise RuntimeError(
            "DEBUG=true is not allowed when ENV=production. "
            "Set DEBUG=false before deploying."
        )

    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required when ENV=production")

    if _database_password(settings) == WEAK_DB_PASSWORD:
        raise RuntimeError(
            "Default database password is not allowed in production. "
            "Set a strong MYSQL_PASSWORD or DATABASE_URL."
        )

    if settings.webapp_url.startswith("http://"):
        raise RuntimeError(
            "WEBAPP_URL must use HTTPS in production (Telegram Mini Apps requirement)."
        )

    if settings.cors_origins_raw.strip() == "*":
        raise RuntimeError(
            "CORS_ORIGINS must be set to your domain in production (not '*')."
        )
