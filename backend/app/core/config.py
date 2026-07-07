from pathlib import Path

from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import PROJECT_ROOT, resolve_data_dir, resolve_frontend_dir


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "TG Task Tracker"
    debug: bool = False
    environment: str = Field(default="development", validation_alias="ENV")

    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")

    mysql_db: str = Field(
        default="tasktracker",
        validation_alias=AliasChoices("MYSQL_DB", "MYSQL_DATABASE"),
    )
    mysql_host: str = Field(default="localhost", validation_alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, validation_alias="MYSQL_PORT")
    mysql_user: str = Field(default="tasktracker", validation_alias="MYSQL_USER")
    mysql_password: str = Field(default="tasktracker", validation_alias="MYSQL_PASSWORD")

    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 480
    db_connect_timeout: int = 10
    db_read_timeout: int = 30
    db_write_timeout: int = 30

    bot_token: str = ""
    webapp_url: str = "http://localhost:8000"

    cors_origins_raw: str = Field(default="*", validation_alias="CORS_ORIGINS")

    data_dir: Path | None = Field(default=None, validation_alias="DATA_DIR")

    max_upload_size: int = 5 * 1024 * 1024
    upload_sign_ttl_seconds: int = 3600

    rate_limit_default: str = "120/minute"
    rate_limit_comments: str = "20/minute"
    rate_limit_uploads: str = "60/minute"

    log_file: str = "application.log"
    log_level: str = "INFO"
    log_max_bytes: int = 5_242_880  # 5 MB
    log_backup_count: int = 5

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]

    @property
    def resolved_data_dir(self) -> Path:
        return resolve_data_dir(self.data_dir)

    @property
    def uploads_dir(self) -> Path:
        return self.resolved_data_dir / "uploads"

    @property
    def log_dir(self) -> Path:
        return self.resolved_data_dir / "logs"

    @property
    def backups_dir(self) -> Path:
        return self.resolved_data_dir / "backups"

    @property
    def frontend_dir(self) -> Path:
        return resolve_frontend_dir()

    @property
    def async_database_url(self) -> str:
        if self.database_url:
            url = self.database_url
            if url.startswith("mysql://"):
                return url.replace("mysql://", "mysql+aiomysql://", 1)
            return url
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
        )

    @property
    def sync_database_url(self) -> str:
        return self.async_database_url.replace("+aiomysql", "+pymysql")

    @property
    def has_bot(self) -> bool:
        return bool(self.bot_token)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"
