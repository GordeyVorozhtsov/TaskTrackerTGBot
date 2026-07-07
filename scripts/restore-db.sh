#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SNAPSHOT="${1:-${SNAPSHOT:-}}"
COMPOSE="${COMPOSE:-docker compose --env-file .env -f deploy/docker-compose.yml}"
BACKUPS_DIR="${BACKUPS_DIR:-$ROOT/data/backups}"

if [[ -z "$SNAPSHOT" ]]; then
  echo "Укажите файл снепшота:"
  echo "  make restore SNAPSHOT=data/backups/tasktracker_YYYY-MM-DD_HHMMSS.sql FORCE=1"
  echo "  ./scripts/restore-db.sh data/backups/tasktracker_....sql"
  exit 1
fi

if [[ ! -f "$SNAPSHOT" ]]; then
  if [[ -f "$BACKUPS_DIR/$SNAPSHOT" ]]; then
    SNAPSHOT="$BACKUPS_DIR/$SNAPSHOT"
  else
    echo "Файл не найден: $SNAPSHOT"
    exit 1
  fi
fi

if [[ ! -f .env ]]; then
  echo "Файл .env не найден в $ROOT"
  exit 1
fi

if ! $COMPOSE ps db --status running -q 2>/dev/null | grep -q .; then
  echo "Контейнер MySQL не запущен. Выполните: make db"
  exit 1
fi

if [[ "${FORCE:-}" != "1" ]]; then
  echo "Восстановление перезапишет текущую БД из:"
  echo "  $SNAPSHOT"
  echo "Остановите приложение (make down) перед восстановлением."
  echo "Для подтверждения: FORCE=1 make restore SNAPSHOT=..."
  exit 1
fi

echo "Остановка app-контейнера (если запущен)..."
$COMPOSE stop app 2>/dev/null || true

echo "Восстановление из $SNAPSHOT ..."
$COMPOSE exec -T db sh -c \
  'mysql -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' <"$SNAPSHOT"

echo "Готово. Запустите приложение: make up"
