#!/usr/bin/env bash
# Деплой на Beget shared hosting (без Docker): venv + uvicorn + MySQL localhost.
# Запускать из корня репозитория на сервере.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VENV="$ROOT/.venv"
PID_FILE="$ROOT/data/app.pid"
LOG_FILE="$ROOT/data/logs/uvicorn.stdout.log"
HOST="${APP_HOST:-127.0.0.1}"
PORT="${APP_PORT:-8000}"

if [[ ! -f .env ]]; then
  echo "Нет .env. Скопируйте шаблон: cp .env.beget.example .env && nano .env"
  echo "Для shared Beget в DATABASE_URL используйте localhost (не host.docker.internal)."
  exit 1
fi

mkdir -p data/logs data/uploads data/backups

# Python 3.11+ (на Beget часто python3.10 / python3.11)
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    ver="$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    major="${ver%%.*}"
    minor="${ver#*.}"
    if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
      PYTHON="$candidate"
      break
    fi
  fi
done

if [[ -z "$PYTHON" ]]; then
  echo "Нужен Python 3.10+. Установленные: $(ls /usr/bin/python3* 2>/dev/null || echo 'не найдены')"
  exit 1
fi

echo "==> Python: $($PYTHON --version)"

if [[ ! -d "$VENV" ]]; then
  echo "==> Создание venv..."
  "$PYTHON" -m venv "$VENV"
fi

echo "==> Установка зависимостей..."
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r backend/requirements.txt

echo "==> Миграции..."
cd backend
../"$VENV/bin/alembic" upgrade head
cd "$ROOT"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE")"
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "==> Остановка предыдущего процесса ($old_pid)..."
    bash scripts/stop-beget-native.sh
  else
    rm -f "$PID_FILE"
  fi
fi

echo "==> Запуск uvicorn на ${HOST}:${PORT}..."
nohup "$VENV/bin/uvicorn" app.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --app-dir backend \
  >> "$LOG_FILE" 2>&1 &

echo $! > "$PID_FILE"
sleep 3

if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Процесс упал сразу после старта. Последние строки лога:"
  tail -40 "$LOG_FILE"
  rm -f "$PID_FILE"
  exit 1
fi

echo "==> Ожидание /api/health..."
for i in $(seq 1 30); do
  if curl -sf "http://${HOST}:${PORT}/api/health" >/dev/null 2>&1; then
    echo "OK: http://${HOST}:${PORT}/api/health"
    echo "PID: $(cat "$PID_FILE")"
    echo "Логи: tail -f data/logs/application.log"
    echo "Stdout: tail -f data/logs/uvicorn.stdout.log"
    exit 0
  fi
  if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Процесс завершился. Лог:"
    tail -40 "$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
  fi
  sleep 2
done

echo "Healthcheck не прошёл за 60 с. Лог:"
tail -40 "$LOG_FILE"
exit 1
