#!/usr/bin/env bash
# Beget shared (mayday): запуск без Docker/venv. pip install --user
#   bash scripts/deploy-beget-native.sh        — установить и запустить
#   bash scripts/deploy-beget-native.sh stop   — остановить
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export BEGET_ROOT_DIR="$ROOT"

PID_FILE="$ROOT/data/app.pid"
LOG_FILE="$ROOT/data/logs/uvicorn.stdout.log"
HOST="${APP_HOST:-127.0.0.1}"
PORT="${APP_PORT:-8000}"

_env() { grep -E "^${1}=" .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\r'; }

_find_python() {
  for c in python3.10 python3.11 python3.12 python3; do
    command -v "$c" >/dev/null 2>&1 && echo "$c" && return 0
  done
  return 1
}

_stop() {
  [[ -f "$PID_FILE" ]] || { echo "Не запущено"; return 0; }
  pid="$(cat "$PID_FILE")"
  kill -0 "$pid" 2>/dev/null && kill "$pid" && echo "Остановлено PID $pid"
  rm -f "$PID_FILE"
}

_start() {
  [[ -f .env ]] || { echo "Нет .env — cp .env.beget.example .env && nano .env"; exit 1; }

  db="$(_env DATABASE_URL)"
  [[ -n "$db" && "$db" != *host.docker.internal* ]] || {
    echo "DATABASE_URL=mysql://gvoroz2u_db:ПАРОЛЬ@localhost:3306/gvoroz2u_db"
    exit 1
  }

  mkdir -p data/logs data/uploads data/backups
  PYTHON="$(_find_python)" || { echo "Нужен Python 3.10+"; exit 1; }
  echo "==> $($PYTHON --version)"

  export PATH="$HOME/.local/bin:$PATH"
  "$PYTHON" -m pip install --user -q --upgrade pip
  "$PYTHON" -m pip install --user -q -r backend/requirements.txt

  echo "==> Миграции..."
  (cd backend && PYTHONPATH=. "$PYTHON" -m alembic upgrade head)

  _stop 2>/dev/null || true

  echo "==> Запуск :${PORT}..."
  nohup "$PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --app-dir backend >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  sleep 4

  curl -sf "http://${HOST}:${PORT}/api/health" >/dev/null || {
    tail -30 "$LOG_FILE"
    exit 1
  }
  echo "OK  http://${HOST}:${PORT}/api/health  PID $(cat "$PID_FILE")"
  echo "Логи: tail -f data/logs/application.log"
}

case "${1:-start}" in
  stop) _stop ;;
  *)    _start ;;
esac
