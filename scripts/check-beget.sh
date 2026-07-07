#!/usr/bin/env bash
# Проверка окружения Beget shared перед деплоем.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=scripts/beget-common.sh
source "$ROOT/scripts/beget-common.sh"

OK=0
WARN=0
FAIL=0

pass() { echo "  [OK]   $*"; OK=$((OK + 1)); }
warn() { echo "  [WARN] $*"; WARN=$((WARN + 1)); }
fail() { echo "  [FAIL] $*"; FAIL=$((FAIL + 1)); }

echo "=== Проверка Beget shared ==="
echo ""

# Python
if PYTHON="$(beget_find_python)"; then
  pass "Python: $($PYTHON --version)"
else
  fail "Python 3.10+ не найден"
  PYTHON=""
fi

# pip
if [[ -n "$PYTHON" ]]; then
  if "$PYTHON" -m pip --version >/dev/null 2>&1; then
    pass "pip доступен"
  else
    warn "pip не найден — deploy-beget-native.sh установит через get-pip.py"
  fi
fi

# MySQL
if mysql -h localhost -u gvoroz2u_db -p"${MYSQL_PWD:-}" gvoroz2u_db -e "SELECT 1" >/dev/null 2>&1; then
  pass "MySQL localhost (нужен MYSQL_PWD=... для автопроверки или введите пароль вручную)"
elif mysql -h localhost -u gvoroz2u_db -p gvoroz2u_db -e "SELECT 1" >/dev/null 2>&1; then
  pass "MySQL localhost"
else
  warn "MySQL: проверьте вручную — mysql -h localhost -u gvoroz2u_db -p gvoroz2u_db -e 'SELECT 1'"
fi

# .env
if [[ -f .env ]]; then
  pass ".env существует"
  if grep -q 'host.docker.internal' .env; then
    fail ".env: замените host.docker.internal на localhost"
  fi
  if grep -q 'ENV=production' .env && grep -q 'DEBUG=true' .env; then
    fail ".env: DEBUG=true нельзя при ENV=production"
  fi
  if ! grep -q 'BOT_TOKEN=.' .env; then
    warn ".env: BOT_TOKEN пустой"
  fi
else
  fail ".env не найден — cp .env.beget.example .env"
fi

# Docker (не нужен)
if docker info >/dev/null 2>&1; then
  warn "Docker доступен — на shared Beget используйте deploy-beget-native.sh, не Docker"
else
  pass "Docker недоступен — это нормально для shared Beget"
fi

# venv (не нужен)
if python3 -m venv /tmp/beget-venv-test 2>/dev/null; then
  rm -rf /tmp/beget-venv-test
  pass "python3-venv доступен (не обязателен)"
else
  pass "python3-venv недоступен — deploy использует pip --user (это нормально)"
fi

# curl
if command -v curl >/dev/null 2>&1; then
  pass "curl установлен"
else
  warn "curl не найден"
fi

# screen (рекомендуется)
if command -v screen >/dev/null 2>&1; then
  pass "screen установлен (рекомендуется для долгоживущего процесса)"
else
  warn "screen не найден — процесс может быть убит при закрытии SSH"
fi

echo ""
echo "Итого: OK=$OK  WARN=$WARN  FAIL=$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  echo "Исправьте FAIL перед деплоем."
  exit 1
fi
echo "Можно деплоить: bash scripts/deploy-beget-native.sh"
