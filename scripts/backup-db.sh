#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKUPS_DIR="${BACKUPS_DIR:-$ROOT/data/backups}"
SNAPSHOT_KEEP="${SNAPSHOT_KEEP:-10}"
COMPOSE="${COMPOSE:-docker compose --env-file .env -f deploy/docker-compose.yml}"

if [[ ! -f .env ]]; then
  echo "Файл .env не найден в $ROOT"
  exit 1
fi

if ! $COMPOSE ps db --status running -q 2>/dev/null | grep -q .; then
  echo "Контейнер MySQL не запущен. Выполните: make db"
  exit 1
fi

mkdir -p "$BACKUPS_DIR"
TIMESTAMP="$(date +%Y-%m-%d_%H%M%S)"
FILE="$BACKUPS_DIR/tasktracker_${TIMESTAMP}.sql"

echo "Создание снепшота: $FILE"
$COMPOSE exec -T db sh -c \
  'mysqldump -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" --single-transaction --routines --triggers' \
  >"$FILE"

BYTES="$(wc -c <"$FILE" | tr -d ' ')"
if [[ "$BYTES" -lt 100 ]]; then
  echo "Ошибка: снепшот слишком маленький ($BYTES байт)"
  rm -f "$FILE"
  exit 1
fi

echo "Готово: $FILE ($(du -h "$FILE" | cut -f1))"

if [[ "$SNAPSHOT_KEEP" =~ ^[0-9]+$ ]] && [[ "$SNAPSHOT_KEEP" -gt 0 ]]; then
  OLD="$(ls -1t "$BACKUPS_DIR"/tasktracker_*.sql 2>/dev/null | tail -n +"$((SNAPSHOT_KEEP + 1))" || true)"
  if [[ -n "$OLD" ]]; then
    echo "Удаление старых снепшотов (храним последние $SNAPSHOT_KEEP):"
    while IFS= read -r path; do
      [[ -z "$path" ]] && continue
      rm -f "$path"
      echo "  - $path"
    done <<<"$OLD"
  fi
fi
