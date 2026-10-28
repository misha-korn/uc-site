#!/bin/sh
# Точка входа контейнера: ждём БД, применяем миграции, собираем статику, запускаем команду.
set -eu

cd /app

# Если контейнер запущен от root (PaaS с постоянным диском): готовим папки для SQLite и
# загруженных файлов, отдаём их пользователю app и перезапускаем этот же скрипт от его имени.
if [ "$(id -u)" = "0" ] && id app >/dev/null 2>&1; then
  for dir in "${MEDIA_ROOT:-/app/media}" "${STATIC_ROOT:-/app/staticfiles}"; do
    mkdir -p "$dir" && chown -R app:app "$dir"
  done
  case "${DATABASE_URL:-}" in
    sqlite:///*)
      db_file="${DATABASE_URL#sqlite://}"
      mkdir -p "$(dirname "$db_file")"
      chown app:app "$(dirname "$db_file")"
      if [ -f "$db_file" ]; then chown app:app "$db_file"; fi
      ;;
  esac
  exec setpriv --reuid=app --regid=app --init-groups "$0" "$@"
fi

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
