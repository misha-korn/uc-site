#!/bin/sh
# Точка входа контейнера: ждём БД, применяем миграции, собираем статику, запускаем команду.
set -eu

cd /app

if [ -n "${DATABASE_URL:-}" ]; then
  echo "[entrypoint] Ожидание базы данных..."
  python - <<'PY'
import sys, time
import django
django.setup()
from django.db import connection
for attempt in range(60):
    try:
        connection.ensure_connection()
        print("[entrypoint] База данных доступна")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"[entrypoint] БД ещё недоступна ({exc.__class__.__name__}), попытка {attempt + 1}/60")
        time.sleep(2)
print("[entrypoint] Не дождались базы данных", file=sys.stderr)
sys.exit(1)
PY
fi

if [ "${SKIP_MIGRATE:-0}" != "1" ]; then
  echo "[entrypoint] Применение миграций"
  python manage.py migrate --noinput
fi

# Статика копируется в общий том (его раздаёт nginx). Быстро: копируются только изменённые файлы.
if [ "${SKIP_COLLECTSTATIC:-0}" != "1" ]; then
  python manage.py collectstatic --noinput --verbosity 0
fi

# Демо-наполнение по желанию: SEED_DEMO=1 в .env (только для демо-стенда!)
if [ "${SEED_DEMO:-0}" = "1" ]; then
  echo "[entrypoint] Загрузка демо-данных"
  python manage.py seed_demo || echo "[entrypoint] seed_demo завершился с ошибкой — продолжаю"
fi

exec "$@"
