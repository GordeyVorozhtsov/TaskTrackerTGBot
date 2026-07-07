#!/usr/bin/env bash
# Деплой на Beget SHARED (mayday): без Docker, без sudo, без python3-venv.
# Использует pip install --user → ~/.local/bin
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export BEGET_ROOT_DIR="$ROOT"

# shellcheck source=scripts/beget-common.sh
source "$ROOT/scripts/beget-common.sh"

PID_FILE="$ROOT/data/app.pid"
LOG_FILE="$ROOT/data/logs/uvicorn.stdout.log"
HOST="${APP_HOST:-127.0.0.1}"
PORT="${APP_PORT:-8000}"

if [[ ! -f .env ]]; then
  echo "Нет .env. Выполните: cp .env.beget.example .env && nano .env"
  exit 1
fi

if grep -q 'host.docker.internal' .env 2>/dev/null; then
  echo "ОШИБКА: в .env для shared Beget нужен localhost, не host.docker.internal"
  echo "  DATABASE_URL=mysql://gvoroz2u_db:ПАРОЛЬ@localhost:3306/gvoroz2u_db"
  exit 1
fi

mkdir -p data/logs data/uploads data/backups

PYTHON="$(beget_find_python)" || {
  echo "Нужен Python 3.10+. Проверьте: python3 --version"
  exit 1
}
echo "==> Python: $($PYTHON --version)"

beget_setup_path "$PYTHON"
beget_install_deps "$PYTHON" "$ROOT"
beget_run_migrations "$PYTHON" "$ROOT"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "==> Остановка предыдущего процесса..."
  bash "$ROOT/scripts/stop-beget-native.sh"
fi

echo "==> Запуск uvicorn на ${HOST}:${PORT}..."
nohup "$PYTHON" -m uvicorn app.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --app-dir "$ROOT/backend" \
  >> "$LOG_FILE" 2>&1 &

echo $! > "$PID_FILE"
sleep 4

if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Процесс упал сразу после старта:"
  tail -50 "$LOG_FILE"
  rm -f "$PID_FILE"
  exit 1
fi

echo "==> Ожидание /api/health..."
for _ in $(seq 1 30); do
  if curl -sf "http://${HOST}:${PORT}/api/health" >/dev/null 2>&1; then
    echo ""
    echo "============================================"
    echo "  OK: http://${HOST}:${PORT}/api/health"
    echo "  PID: $(cat "$PID_FILE")"
    echo "  Логи: tail -f data/logs/application.log"
    echo "  Stdout: tail -f data/logs/uvicorn.stdout.log"
    echo "============================================"
    exit 0
  fi
  if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Процесс завершился:"
    tail -50 "$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
  fi
  sleep 2
done

echo "Healthcheck не прошёл. Лог:"
tail -50 "$LOG_FILE"
exit 1
