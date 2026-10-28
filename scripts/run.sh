#!/usr/bin/env bash
# Запуск сайта для разработки:  ./scripts/run.sh   (или ./scripts/run.sh django)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ -x .venv/bin/python ]] || { echo "Сначала выполните ./scripts/setup.sh"; exit 1; }
VPY=.venv/bin/python
"$VPY" manage.py migrate --noinput
echo "Сайт: http://127.0.0.1:8000/   Панель: http://127.0.0.1:8000/admin/   Остановить: Ctrl+C"
if [[ "${1:-}" == "django" ]]; then
  exec "$VPY" manage.py runserver 127.0.0.1:8000
else
  exec "$VPY" -m uvicorn config.asgi:application --reload --host 127.0.0.1 --port 8000
fi
