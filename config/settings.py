"""
Настройки Django-проекта сайта учебного центра.

Все «секретные» и зависящие от сервера значения берутся из переменных
окружения (файл .env в корне проекта подхватывается автоматически через
python-dotenv). Список переменных — в CONTRACT.md, п. 10, и в .env.example.

Коротко для новичка:
- локально достаточно ничего не задавать: DEBUG=1 по умолчанию, база SQLite;
- на сервере ОБЯЗАТЕЛЬНО: DEBUG=0, SECRET_KEY, ALLOWED_HOSTS, DATABASE_URL, SITE_URL.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# .env не перезаписывает переменные, уже заданные в окружении (docker, systemd).
load_dotenv(BASE_DIR / ".env", override=False)


# --- Помощники для чтения переменных окружения ------------------------------

def env_str(name, default=""):
    """Строка из окружения (пробелы по краям обрезаются)."""
    return os.environ.get(name, default).strip()


def env_bool(name, default=False):
    """Логическое значение: 1/true/yes/on → True, 0/false/no/off/'' → False."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "да"}


def env_int(name, default=0):
    """Целое число из окружения; при ошибке — понятное сообщение."""
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(f"Переменная {name} должна быть целым числом, сейчас: {value!r}") from exc


def env_list(name, default=None):
    """Список через запятую: 'a.ru, b.ru' → ['a.ru', 'b.ru']."""
    value = os.environ.get(name)
    if value is None:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


# --- Основное ---------------------------------------------------------------

# По умолчанию DEBUG включён, чтобы проект запускался «из коробки» локально.
# На сервере devops обязательно ставит DEBUG=0 (см. .env.example / docker-compose).
DEBUG = env_bool("DEBUG", True)

SECRET_KEY = env_str("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        # Только для локальной разработки! В проде без SECRET_KEY запуск невозможен.
        SECRET_KEY = "django-insecure-local-dev-key-do-not-use-in-production"
    else:
        raise ImproperlyConfigured(
            "Не задана переменная окружения SECRET_KEY (обязательна при DEBUG=0). "
            "Сгенерируйте ключ командой: "
            "python -c \"from django.core.management.utils import get_random_secret_key as g; print(g())\" "
            "и пропишите его в .env: SECRET_KEY=..."
        )

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", ["localhost", "127.0.0.1", "[::1]"] if DEBUG else [])

# Публичный адрес сайта без слеша на конце, напр. https://uc-profresurs.ru.
# Нужен для ссылок в уведомлениях о заявках и для sitemap.xml.
SITE_URL = env_str("SITE_URL").rstrip("/")

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
if not CSRF_TRUSTED_ORIGINS and SITE_URL.startswith(("http://", "https://")):
    CSRF_TRUSTED_ORIGINS = [SITE_URL]

# Демо-режим: плашка «Демо-версия, данные вымышленные», media отдаёт Django,
# robots.txt запрещает индексацию.
SITE_DEMO = env_bool("SITE_DEMO", False)

# Версия текста согласия на обработку ПДн — сохраняется в каждой заявке.
CONSENT_VERSION = env_str("CONSENT_VERSION", "1.0 от 27.10.2026")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    # runserver не будет сам раздавать статику — это делает WhiteNoise (как в проде)
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "core.apps.CoreConfig",
    "sveden.apps.SvedenConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # CSP + Permissions-Policy (настройки — в блоке «Безопасность» ниже)
    "core.middleware.SecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# --- База данных ------------------------------------------------------------
# Локально — SQLite, на сервере — PostgreSQL: DATABASE_URL=postgres://user:pass@host:5432/db
# В async-режиме (ASGI) постоянные соединения не используем (CONN_MAX_AGE=0 по умолчанию):
# так рекомендует документация Django для async views.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=env_int("DB_CONN_MAX_AGE", 0),
        conn_health_checks=True,
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Пароли -----------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Язык и время -----------------------------------------------------------
LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Samara"
USE_I18N = True
USE_TZ = True


# --- Статика и медиа ----------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = Path(env_str("STATIC_ROOT") or BASE_DIR / "staticfiles")
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").is_dir() else []

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env_str("MEDIA_ROOT") or BASE_DIR / "media")

# В проде (DEBUG=0) статику сжимаем и добавляем хеш в имя файла (кеш навсегда).
# Перед запуском обязательно: python manage.py collectstatic --noinput
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}
# Если какого-то файла нет в манифесте — не роняем страницу ошибкой 500.
WHITENOISE_MANIFEST_STRICT = False
# Под uvicorn в режиме разработки WhiteNoise отдаёт файлы прямо из static/.
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG

# Файлы из MEDIA (документы, PDF) в проде отдаёт nginx. Django отдаёт их сам
# только при DEBUG=1, в демо-режиме (SITE_DEMO=1) или если явно SERVE_MEDIA=1.
SERVE_MEDIA = DEBUG or SITE_DEMO or env_bool("SERVE_MEDIA", False)

FILE_UPLOAD_PERMISSIONS = 0o644
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 МБ — защита от огромных POST

# Шрифт с кириллицей для генерации демо-PDF (в Docker: пакет fonts-dejavu-core).
PDF_FONT_PATH = env_str("PDF_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


# --- Кеш (используется для ограничения частоты заявок) ----------------------
# LocMem хранит данные в памяти процесса. Если uvicorn запущен с несколькими
# воркерами, лимит считается в каждом воркере отдельно — для сайта-визитки это нормально.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "uc-site",
    }
}

# Лимит заявок: не более LEAD_RATE_LIMIT за LEAD_RATE_WINDOW секунд с одного IP.
LEAD_RATE_LIMIT = env_int("LEAD_RATE_LIMIT", 5)
LEAD_RATE_WINDOW = env_int("LEAD_RATE_WINDOW", 600)

# Доверять заголовку X-Forwarded-For (только если сайт стоит за своим nginx!).
USE_X_FORWARDED_FOR = env_bool("USE_X_FORWARDED_FOR", False)


# --- Почта и уведомления о заявках ------------------------------------------
EMAIL_HOST = env_str("EMAIL_HOST")
EMAIL_PORT = env_int("EMAIL_PORT", 465)
EMAIL_HOST_USER = env_str("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD")
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", True)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False) and not EMAIL_USE_SSL
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 5)
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL") or EMAIL_HOST_USER or "webmaster@localhost"
SERVER_EMAIL = DEFAULT_FROM_EMAIL
if not EMAIL_HOST:
    # Почта не настроена — письма (если вдруг будут) печатаются в консоль.
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
LEADS_EMAIL_TO = env_list("LEADS_EMAIL_TO")

TELEGRAM_BOT_TOKEN = env_str("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = env_str("TELEGRAM_CHAT_ID")
# Сколько максимум ждём отправки уведомлений, прежде чем ответить посетителю.
NOTIFY_TIMEOUT = env_int("NOTIFY_TIMEOUT", 5)


# --- Безопасность -----------------------------------------------------------
# За nginx: он передаёт X-Forwarded-Proto: https — Django понимает, что запрос по HTTPS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
# После входа в /admin/login/ с подменённым ?next=//evil… Django отбрасывает небезопасный адрес и
# ведёт на LOGIN_REDIRECT_URL. Отдельного «личного кабинета» нет — значит, в панель.
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

if not DEBUG:
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
    CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)
    # HSTS: браузер запомнит, что сайт работает только по HTTPS.
    # Для первого запуска можно поставить SECURE_HSTS_SECONDS=3600, потом вернуть год.
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
    # preload — «вшить» домен в списки браузеров. Отменить почти невозможно (месяцы), поэтому
    # по умолчанию ВЫКЛ; включать (SECURE_HSTS_PRELOAD=1) только осознанно, когда HTTPS стабилен навсегда.
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
    if not SECURE_HSTS_PRELOAD:
        # check --deploy предупреждает (security.W021), что preload выключен. Это осознанный выбор —
        # заглушаем только это предупреждение, остальные проверки безопасности работают.
        SILENCED_SYSTEM_CHECKS = ["security.W021"]

# Content-Security-Policy (core/middleware.py). Браузер выполняет только наши файлы из /static/:
# ни inline-скриптов, ни CDN, ни внешних шрифтов. Чужие ресурсы на сайте = передача IP посетителя
# третьим лицам, поэтому каждый новый домен сюда — только вместе с правкой Политики ПДн.
# Карта на «Контактах» — iframe Яндекс Карт (поле «Код карты» у организации), поэтому frame-src.
CSP_DIRECTIVES = {
    "default-src": ["'self'"],
    "script-src": ["'self'"],
    "style-src": ["'self'"],
    "img-src": ["'self'", "data:"],
    "font-src": ["'self'"],
    "connect-src": ["'self'"],
    "frame-src": ["https://yandex.ru", "https://*.yandex.ru"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
    "base-uri": ["'self'"],
    "object-src": ["'none'"],
}
# Панель /admin/: то же, но со style-атрибутами (цветные статусы заявок, виджеты Django admin).
CSP_ADMIN_DIRECTIVES = {**CSP_DIRECTIVES, "style-src": ["'self'", "'unsafe-inline'"]}
CSP_ADMIN_PREFIX = "/admin/"
# 1 — только отчёт в консоли браузера, без блокировки (для отладки нового внешнего сервиса).
CSP_REPORT_ONLY = env_bool("CSP_REPORT_ONLY", False)
# Сайту не нужны камера, микрофон, геолокация, платежи, USB и датчики — запрещаем всем, в т. ч. iframe.
PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), "
    "microphone=(), payment=(), usb=()"
)

# --- Персональные данные (152-ФЗ): срок хранения заявок -----------------------
# Должен совпадать с Политикой и Согласием (templates/legal/*): «1 год с даты заявки».
# Команда `python manage.py purge_leads` (по cron/systemd-таймеру раз в сутки) удаляет заявки старше срока.
LEAD_RETENTION_DAYS = env_int("LEAD_RETENTION_DAYS", 365)
# Заявки со статусом «Спам» удаляются раньше — цель обработки отсутствует.
LEAD_SPAM_RETENTION_DAYS = env_int("LEAD_SPAM_RETENTION_DAYS", 30)


# --- Логирование ------------------------------------------------------------
LOG_LEVEL = env_str("LOG_LEVEL", "INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        # 4xx (404, 403) — уровень WARNING: в лог не пишем, чтобы не засорять; 5xx (ERROR) — пишем.
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "core": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "sveden": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
