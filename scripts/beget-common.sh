#!/usr/bin/env bash
# Общие функции для деплоя на Beget shared (без sudo, Docker, venv).
set -euo pipefail

beget_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

beget_find_python() {
  local candidate ver major minor
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      ver="$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
      major="${ver%%.*}"
      minor="${ver#*.}"
      if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
        echo "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

beget_bootstrap_pip() {
  local python="$1"
  if "$python" -m pip --version >/dev/null 2>&1; then
    return 0
  fi
  echo "==> pip не найден, установка через get-pip.py (--user)..."
  local tmp
  tmp="$(mktemp /tmp/get-pip.XXXXXX.py)"
  curl -fsSL "https://bootstrap.pypa.io/pip/3.10/get-pip.py" -o "$tmp"
  "$python" "$tmp" --user
  rm -f "$tmp"
}

beget_setup_path() {
  local python="$1"
  export PATH="$HOME/.local/bin:$PATH"
  export PYTHONPATH="${BEGET_ROOT_DIR:-}/backend${PYTHONPATH:+:$PYTHONPATH}"
  export PYTHONUSERBASE="${HOME}/.local"
  # uv / pip --user кладут бинарники сюда
  if ! "$python" -m pip --version >/dev/null 2>&1; then
    beget_bootstrap_pip "$python"
  fi
}

beget_install_deps() {
  local python="$1"
  local root="$2"
  echo "==> Установка зависимостей (pip --user, без venv/sudo)..."
  "$python" -m pip install --user --upgrade pip
  "$python" -m pip install --user -r "$root/backend/requirements.txt"
}

beget_run_migrations() {
  local python="$1"
  local root="$2"
  echo "==> Миграции Alembic..."
  (cd "$root/backend" && PYTHONPATH=. "$python" -m alembic upgrade head)
}
