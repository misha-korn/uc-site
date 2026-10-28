#!/usr/bin/env bash
# =====================================================================
#  Резервная копия базы данных и загруженных файлов (media).
#
#  VPS без Docker:      ./scripts/backup_db.sh
#  Docker Compose:      ./scripts/backup_db.sh --docker
#  Восстановление:      см. DEPLOY.md, раздел «Бэкапы».
#
#  Переменные: BACKUP_DIR (по умолчанию ./backups), KEEP_DAYS (14),
#  DATABASE_URL (берётся из .env, если не задана).
# =====================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

MODE="local"
[[ "${1:-}" == "--docker" ]] && MODE="docker"

# Подхватываем .env (только простые строки KEY=VALUE)
if [[ -f .env ]]; then
  while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
    key="$(echo "$key" | tr -d '[:space:]')"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ -z "${!key:-}" ]]; then
      value="${value%\"}"; value="${value#\"}"
      export "$key=$value"
    fi
  done < .env
fi

BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y-%m-%d_%H-%M)"
mkdir -p "$BACKUP_DIR"
umask 077

log() { echo "[$(date '+%F %T')] $*"; }

if [[ "$MODE" == "docker" ]]; then
  DB_FILE="$BACKUP_DIR/db_${STAMP}.sql.gz"
  log "Дамп PostgreSQL из контейнера db -> $DB_FILE"
  docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --clean --if-exists' \
    | gzip -9 > "$DB_FILE"
  MEDIA_FILE="$BACKUP_DIR/media_${STAMP}.tar.gz"
  log "Архив media -> $MEDIA_FILE"
  docker compose exec -T web tar -C /app -czf - media > "$MEDIA_FILE"
else
  DB_URL="${DATABASE_URL:-}"
  if [[ "$DB_URL" == postgres://* || "$DB_URL" == postgresql://* ]]; then
    DB_FILE="$BACKUP_DIR/db_${STAMP}.sql.gz"
    log "Дамп PostgreSQL -> $DB_FILE"
    pg_dump --dbname="$DB_URL" --no-owner --clean --if-exists | gzip -9 > "$DB_FILE"
  else
    # SQLite: путь из sqlite:////abs/path или db.sqlite3 по умолчанию
    SQLITE_PATH="db.sqlite3"
    if [[ "$DB_URL" == sqlite:///* ]]; then
      SQLITE_PATH="${DB_URL#sqlite:///}"
    fi
    DB_FILE="$BACKUP_DIR/db_${STAMP}.sqlite3.gz"
    log "Копия SQLite ($SQLITE_PATH) -> $DB_FILE"
    TMP="$(mktemp)"
    python3 - "$SQLITE_PATH" "$TMP" <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1]); dst = sqlite3.connect(sys.argv[2])
src.backup(dst); dst.close(); src.close()
PY
    gzip -9c "$TMP" > "$DB_FILE"; rm -f "$TMP"
  fi
  if [[ -d media ]]; then
    MEDIA_FILE="$BACKUP_DIR/media_${STAMP}.tar.gz"
    log "Архив media -> $MEDIA_FILE"
    tar -czf "$MEDIA_FILE" media
  fi
fi

log "Удаление бэкапов старше ${KEEP_DAYS} дн."
find "$BACKUP_DIR" -maxdepth 1 -type f \( -name 'db_*' -o -name 'media_*' \) -mtime +"$KEEP_DAYS" -delete

log "Готово:"
ls -lh "$BACKUP_DIR" | tail -n 6
