#!/usr/bin/env bash
# Деплой на Beget VPS (Docker). На shared-хостинге Docker недоступен — используйте deploy-beget-native.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE="docker compose --env-file .env -f deploy/docker-compose.beget.yml"

if [[ ! -f .env ]]; then
  echo "Нет .env. Скопируйте шаблон: cp .env.beget.example .env && nano .env"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker недоступен для текущего пользователя."
  echo ""
  echo "Вариант A — shared Beget (mayday), без Docker:"
  echo "  bash scripts/deploy-beget-native.sh"
  echo ""
  echo "Вариант B — VPS, выдать права Docker:"
  echo "  sudo usermod -aG docker \$USER"
  echo "  # перелогиниться по SSH, затем снова bash scripts/deploy-beget.sh"
  echo ""
  echo "Вариант C — разово через sudo:"
  echo "  sudo docker compose --env-file .env -f deploy/docker-compose.beget.yml up -d --build"
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
