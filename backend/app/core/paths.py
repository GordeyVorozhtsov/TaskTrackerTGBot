from pathlib import Path

# backend/app/core/paths.py → parents: core(0), app(1), backend(2), project root(3)
_CORE_DIR = Path(__file__).resolve().parent
APP_DIR = _CORE_DIR.parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

FRONTEND_DIR = PROJECT_ROOT / "frontend"
DEPLOY_DIR = PROJECT_ROOT / "deploy"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATA_DIR = PROJECT_ROOT / "data"

LOGS_DIR = DATA_DIR / "logs"
UPLOADS_DIR = DATA_DIR / "uploads"
BACKUPS_DIR = DATA_DIR / "backups"

# Docker: frontend монтируется в /app/frontend
DOCKER_FRONTEND_DIR = Path("/app/frontend")


def resolve_frontend_dir() -> Path:
    if DOCKER_FRONTEND_DIR.is_dir():
        return DOCKER_FRONTEND_DIR
    return FRONTEND_DIR


def resolve_data_dir(data_dir: Path | None = None) -> Path:
    if data_dir is not None:
        return data_dir
    return DATA_DIR
