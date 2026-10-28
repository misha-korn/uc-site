# =====================================================================
#  Сайт учебного центра — образ приложения (Django + uvicorn).
#  Сборка:  docker build -t uc-site .
#  Запуск всего стека (БД + сайт + nginx):  docker compose up -d --build
# =====================================================================

# ---------- Этап 1: сборка зависимостей ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip wheel \
 && pip install -r /tmp/requirements.txt


# ---------- Этап 2: финальный образ ----------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="uc-site" \
      org.opencontainers.image.description="Сайт учебного центра (Приказ Рособрнадзора № 1493)"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings \
    PORT=8000 \
    WEB_CONCURRENCY=1

# libpq5 — для PostgreSQL, fonts-dejavu-core — кириллический шрифт для демо-PDF (reportlab), tini — корректная остановка
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 fonts-dejavu-core tini \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 1000 app \
 && useradd --system --uid 1000 --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app . /app

# Статика собирается при сборке образа (WhiteNoise + общий том для nginx)
RUN SECRET_KEY=build-only-not-secret DEBUG=0 ALLOWED_HOSTS=localhost DATABASE_URL=sqlite:////tmp/build.sqlite3 \
    python manage.py collectstatic --noinput \
 && mkdir -p /app/media /app/staticfiles \
 && chmod +x /app/deploy/entrypoint.sh \
 && chown -R app:app /app/media /app/staticfiles \
 && rm -f /tmp/build.sqlite3

# Контейнер стартует от root только для подготовки папок на постоянном диске
# (на PaaS вроде Amvera /data принадлежит root); entrypoint сразу переходит на пользователя app.
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD ["python", "/app/deploy/healthcheck.py"]

ENTRYPOINT ["/usr/bin/tini", "--", "/app/deploy/entrypoint.sh"]
CMD ["sh", "-c", "exec uvicorn config.asgi:application --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips='*' --no-server-header"]
