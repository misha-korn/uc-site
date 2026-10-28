#!/usr/bin/env bash
# Первая установка сайта на Linux / macOS:  ./scripts/setup.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null || { echo "Python 3.12+ не найден"; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' \
  || echo "ВНИМАНИЕ: нужен Python 3.12+, у вас $("$PY" --version)"

echo "=== 1/5 Виртуальное окружение .venv ==="
[[ -x .venv/bin/python ]] || "$PY" -m venv .venv
VPY=.venv/bin/python

echo "=== 2/5 Зависимости ==="
"$VPY" -m pip install --upgrade pip
"$VPY" -m pip install -r requirements.txt

echo "=== 3/5 Файл настроек .env ==="
if [[ ! -f .env ]]; then
  cp .env.example .env
  KEY="$("$VPY" -c 'import secrets; print(secrets.token_urlsafe(50))')"
  NEWKEY="$KEY" "$VPY" - <<'PY'
import os, pathlib
p = pathlib.Path(".env")
t = p.read_text(encoding="utf-8")
p.write_text(t.replace("SECRET_KEY=change-me-to-a-long-random-string", "SECRET_KEY=" + os.environ["NEWKEY"], 1), encoding="utf-8")
PY
  echo "Создан .env с новым SECRET_KEY"
else
  echo ".env уже есть — не трогаю"
fi

echo "=== 4/5 База данных и демо-данные ==="
"$VPY" manage.py migrate
"$VPY" manage.py seed_demo || echo "ВНИМАНИЕ: seed_demo не выполнился — сайт будет пустым"

echo "=== 5/5 Пользователь панели /admin/ ==="
"$VPY" manage.py createsuperuser || true

echo
echo "Готово! Запуск: ./scripts/run.sh  ->  http://127.0.0.1:8000/"
