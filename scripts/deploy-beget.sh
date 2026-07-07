#!/usr/bin/env bash
# Деплой / обновление на Beget VPS. Запускать из корня репозитория на сервере.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE="docker compose --env-file .env -f deploy/docker-compose.beget.yml"

if [[ ! -f .env ]]; then
  echo "Нет .env. Скопируйте шаблон: cp .env.beget.example .env && nano .env"
  exit 1
fi

mkdir -p data/logs data/uploads data/backups

echo "==> Сборка и запуск приложения..."
$COMPOSE up -d --build

echo "==> Ожидание healthcheck..."
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    echo "OK: /api/health"
    $COMPOSE ps
    exit 0
  fi
  sleep 2
done

echo "Приложение не ответило за 60 с. Логи:"
$COMPOSE logs --tail=80 app
exit 1
