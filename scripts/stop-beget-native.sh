#!/usr/bin/env bash
# Остановка приложения, запущенного через deploy-beget-native.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT/data/app.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "PID-файл не найден ($PID_FILE). Приложение не запущено?"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  echo "==> Остановка процесса $PID..."
  kill "$PID"
  for _ in $(seq 1 15); do
    kill -0 "$PID" 2>/dev/null || break
    sleep 1
  done
  if kill -0 "$PID" 2>/dev/null; then
    echo "Принудительная остановка..."
    kill -9 "$PID" 2>/dev/null || true
  fi
  echo "OK: остановлено"
else
  echo "Процесс $PID не найден (уже завершён)"
fi

rm -f "$PID_FILE"
