# Развёртывание сайта на сервере

Три варианта — выберите один:

| Вариант | Когда подходит | Сложность |
|---|---|---|
| **A. VPS + Docker Compose** | Свой сервер (Timeweb Cloud, Selectel, REG.RU VPS…), не хочется ставить всё руками | ★★ |
| **B. VPS без Docker** (systemd + nginx + PostgreSQL) | Свой сервер, нужен полный контроль | ★★★ |
| **C. Обычный хостинг с Python** (Beget, Timeweb «виртуальный хостинг») | Самое дешёвое, без root-доступа | ★★ |

Во всех вариантах сайт должен работать по **HTTPS** (на форме собираются персональные данные).

---

## 0. Что подготовить заранее

1. **Домен** (например, `uc-profresurs.ru`) и доступ к его DNS.
2. **Сервер**: Ubuntu 22.04 или 24.04, от 1 ГБ RAM, 10 ГБ диска. Доступ по SSH (`ssh root@IP_СЕРВЕРА`).
3. В DNS домена создайте две A-записи на IP сервера: `@` и `www`. Проверка (через 5–30 минут): `ping uc-profresurs.ru`.
4. Код проекта в Git-репозитории (GitHub/GitLab) **или** архив проекта.

> Ниже везде `example.ru` — замените на свой домен.

---

## A. VPS + Docker Compose (рекомендуется)

### A1. Установить Docker
```bash
ssh root@IP_СЕРВЕРА
apt update && apt -y upgrade
curl -fsSL https://get.docker.com | sh
docker --version && docker compose version
```

### A2. Загрузить проект
```bash
mkdir -p /srv && cd /srv
git clone https://github.com/ВАШ_ЛОГИН/uc-site.git
cd uc-site
```
(Без Git: на своём компьютере `scp uc-site.zip root@IP:/srv/` и на сервере `apt install unzip && unzip uc-site.zip`.)

### A3. Настройки
```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # скопируйте результат
nano .env
```
Минимум, что нужно поменять в `.env`:
```ini
SECRET_KEY=<сгенерированная строка>
DEBUG=0
ALLOWED_HOSTS=example.ru,www.example.ru
CSRF_TRUSTED_ORIGINS=https://example.ru,https://www.example.ru
SITE_URL=https://example.ru
SITE_DEMO=0
POSTGRES_PASSWORD=<длинный пароль базы>
SITE_DOMAIN=example.ru
SECURE_SSL_REDIRECT=0
SECURE_HSTS_SECONDS=3600
```
`SECURE_SSL_REDIRECT=0` — так и оставляйте: на HTTPS переводит nginx, а Django при этом не мешает
проверке certbot.
`DATABASE_URL` в Docker задавать **не нужно** — он собирается из `POSTGRES_*`.
`USE_X_FORWARDED_FOR=1` docker-compose ставит сам (сайт стоит за nginx).
`SITE_DEMO=0` — значение по умолчанию в `.env.example`; `SITE_DEMO=1` ставьте **только на демо-стенде**
(плашка «демо», запрет индексации, `seed_demo --reset` без `--force`).
Остальные переменные можно не трогать: `LEAD_RETENTION_DAYS=365` и `LEAD_SPAM_RETENTION_DAYS=30` (сроки хранения
заявок — как в Политике), `CSP_REPORT_ONLY=0`, `SECURE_HSTS_PRELOAD=0` (preload включайте только осознанно —
отменить его почти невозможно), `MEDIA_ROOT` пусто (= папка `media/` проекта).

> **Число процессов.** Лимит заявок (5 с одного IP за 10 минут) хранится в памяти процесса uvicorn,
> поэтому при `WEB_CONCURRENCY=2` и больше он считается в каждом процессе отдельно (фактически лимит ×N).
> По умолчанию запускается 1 процесс — для сайта учебного центра этого с большим запасом хватает.
Сохранить в nano: `Ctrl+O`, `Enter`, выйти: `Ctrl+X`.

### A4. Запуск
```bash
docker compose up -d --build
docker compose ps                     # все три сервиса должны быть running / healthy
docker compose logs -f web            # логи сайта (выход: Ctrl+C)
docker compose exec web python manage.py createsuperuser   # логин в /admin/
```
Только для демо-стенда: `docker compose exec web python manage.py seed_demo`.
Пароль из `DEMO_ADMIN_PASSWORD` проверяется валидаторами Django: при `SITE_DEMO=0` слабый пароль не принимается
(admin не создаётся). `seed_demo --reset` на сайте с `SITE_DEMO=0` требует флаг `--force` — защита от
случайного удаления всех сведений.

### A5. HTTPS (один nginx в Docker, сертификат certbot)
nginx в Docker слушает 80 и 443 и **сам выбирает режим** (скрипт `deploy/nginx/docker/40-uc-site.sh`):
- сертификата для `SITE_DOMAIN` ещё нет → сайт работает по `http://`, а `/.well-known/acme-challenge/`
  раздаётся из `/var/www/html` хоста — certbot проходит проверку;
- сертификат появился → не позже чем через минуту nginx переключается на HTTPS: `http://` и `www` →
  `https://ДОМЕН`, HTTP/2, TLS 1.2/1.3. Продлённый сертификат подхватывается так же, без перезапуска.

Один раз на сервере:
```bash
sudo apt install -y certbot                       # nginx на хосте НЕ нужен
sudo systemctl disable --now nginx 2>/dev/null    # если ставили — освободить порты 80/443
sudo mkdir -p /var/www/html
```
DNS: A-записи `@` и `www` → IP сервера (`dig +short example.ru`, `dig +short www.example.ru`).

После `docker compose up -d --build`:
```bash
sudo certbot certonly --webroot -w /var/www/html -d example.ru -d www.example.ru \
  -m ваш@email.ru --agree-tos --no-eff-email
docker compose logs nginx | tail -3       # через минуту: «режим nginx: https»
sudo certbot renew --dry-run              # проверка автопродления (таймер certbot на хосте)
```
Нет записи `www` в DNS — уберите `-d www.example.ru`.

### A6. Обновление сайта
```bash
cd /srv/uc-site
./scripts/backup_db.sh --docker      # сначала бэкап!
git pull
docker compose up -d --build         # миграции и collectstatic выполнятся автоматически
docker image prune -f
```

---

## B. VPS без Docker (systemd + nginx + PostgreSQL)

### B1. Пакеты
```bash
apt update && apt -y upgrade
apt install -y python3 python3-venv python3-dev build-essential libpq-dev \
               postgresql nginx certbot python3-certbot-nginx fonts-dejavu-core git
python3 --version    # нужен 3.12+ (Ubuntu 24.04 — 3.12 из коробки)
```
На Ubuntu 22.04 Python 3.12: `add-apt-repository ppa:deadsnakes/ppa && apt install python3.12 python3.12-venv python3.12-dev`
и дальше вместо `python3` пишите `python3.12`.

### B2. Пользователь и код
```bash
adduser --system --group --home /srv/uc-site uc-site
git clone https://github.com/ВАШ_ЛОГИН/uc-site.git /srv/uc-site-src && cp -a /srv/uc-site-src/. /srv/uc-site/ && rm -rf /srv/uc-site-src
mkdir -p /srv/uc-site/media /srv/uc-site/backups
chown -R uc-site:uc-site /srv/uc-site
```

### B3. База данных PostgreSQL
```bash
sudo -u postgres psql <<'SQL'
CREATE USER uc_user WITH PASSWORD 'ДЛИННЫЙ_ПАРОЛЬ';
CREATE DATABASE uc_site OWNER uc_user ENCODING 'UTF8';
SQL
```

### B4. Окружение Python и настройки
```bash
cd /srv/uc-site
sudo -u uc-site python3 -m venv .venv
sudo -u uc-site .venv/bin/pip install -r requirements.txt
sudo -u uc-site cp .env.example .env
sudo -u uc-site nano .env
```
В `.env` — как в A3, плюс:
```ini
DATABASE_URL=postgres://uc_user:ДЛИННЫЙ_ПАРОЛЬ@localhost:5432/uc_site
USE_X_FORWARDED_FOR=1
```
Затем:
```bash
chmod 600 .env
sudo -u uc-site .venv/bin/python manage.py migrate
sudo -u uc-site .venv/bin/python manage.py collectstatic --noinput
sudo -u uc-site .venv/bin/python manage.py createsuperuser
sudo -u uc-site .venv/bin/python manage.py check --deploy
```

### B5. Служба systemd
```bash
cp deploy/systemd/uc-site.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now uc-site
systemctl status uc-site          # должно быть active (running)
curl -I -H "Host: example.ru" -H "X-Forwarded-Proto: https" http://127.0.0.1:8000/robots.txt
```

### B6. nginx + HTTPS
```bash
mkdir -p /etc/nginx/snippets/uc-site
cp deploy/nginx/snippets/*.conf /etc/nginx/snippets/uc-site/
cp deploy/nginx/uc-site.conf /etc/nginx/sites-available/uc-site.conf
sed -i 's/example\.ru/ВАШ-ДОМЕН.ru/g' /etc/nginx/sites-available/uc-site.conf
```
Конфиг ссылается на сертификат, которого ещё нет. Получаем его в два шага:
```bash
# 1) получаем сертификат: стандартный default-конфиг nginx уже отдаёт /var/www/html на 80 порту
certbot certonly --webroot -w /var/www/html -d ВАШ-ДОМЕН.ru -d www.ВАШ-ДОМЕН.ru \
  -m ваш@email.ru --agree-tos --no-eff-email --deploy-hook "systemctl reload nginx"
# 2) выключаем default и включаем конфиг сайта
rm -f /etc/nginx/sites-enabled/default
ln -s /etc/nginx/sites-available/uc-site.conf /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
# 3) проверка автопродления
certbot renew --dry-run
```
Сертификат продлевается автоматически (`systemctl list-timers | grep certbot`).
Перед шагом 1 домен должен указывать на IP сервера (A-записи для `ВАШ-ДОМЕН.ru` и `www`), порты 80 и 443 открыты (`ufw allow 'Nginx Full'`).

Что делает nginx-конфиг: отдаёт `/static/` (кеш 30 дней) и `/media/` (документы PDF) напрямую с диска,
сжимает gzip, добавляет заголовки безопасности (HSTS, nosniff, X-Frame-Options, Referrer-Policy;
CSP и Permissions-Policy ставит сам Django), передаёт в Django `X-Forwarded-Proto` и реальный IP, разрешает
загрузку файлов до 20 МБ (в панели принимаются только документы PDF/DOC/DOCX/XLS/XLSX/ODT/ODS/SIG/P7S и фото
JPG/PNG/WEBP). **Вход в панель `/admin/login/` ограничен: не более 5 попыток в минуту с одного IP** (+5 подряд
«в запас»), сверх лимита nginx отвечает `429` — защита от подбора пароля. Тот же лимит есть в Docker-конфиге
`deploy/nginx/docker/locations.conf`. Если вы сами упёрлись в лимит — подождите минуту.

### B7. Обновление
```bash
cd /srv/uc-site
sudo -u uc-site ./scripts/backup_db.sh
sudo -u uc-site git pull            # или скопируйте новые файлы
sudo -u uc-site .venv/bin/pip install -r requirements.txt
sudo -u uc-site .venv/bin/python manage.py migrate
sudo -u uc-site .venv/bin/python manage.py collectstatic --noinput
systemctl restart uc-site
```

---

## C. Обычный хостинг с Python (Beget, Timeweb)

Подходит, если у хостинга есть Python 3.12+ и SSH. Названия пунктов меню у хостеров меняются —
ориентируйтесь на смысл.

1. В панели хостинга создайте сайт и привяжите домен. Включите бесплатный SSL (Let's Encrypt) — кнопкой в панели.
2. Подключитесь по SSH (данные — в панели), перейдите в папку сайта.
3. Загрузите проект (git clone или архив через файловый менеджер).
4. Создайте окружение: `python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
5. `cp .env.example .env` и заполните, как в A3 (`USE_X_FORWARDED_FOR=0`, если хостинг не гарантирует этот заголовок). База: если хостинг даёт PostgreSQL — `DATABASE_URL=postgres://...`;
   если только MySQL — проще оставить SQLite (`DATABASE_URL=` пусто): для сайта учебного центра этого достаточно.
   Добавьте `SERVE_MEDIA=1`, если хостинг не умеет отдавать папку `media/` сам.
6. `.venv/bin/python manage.py migrate && .venv/bin/python manage.py collectstatic --noinput && .venv/bin/python manage.py createsuperuser`
7. Подключение приложения:
   - **Beget** и другие хостинги с Passenger: в корне сайта файл `passenger_wsgi.py`:
     ```python
     import os, sys
     sys.path.insert(0, os.path.dirname(__file__))
     os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
     from config.wsgi import application
     ```
     и в `.htaccess` укажите путь к Python из `.venv` (`PassengerPython /home/…/.venv/bin/python`) — см. справку хостинга «Django».
   - **Timeweb** (раздел Python/Django в панели) — укажите модуль `config.wsgi:application` и путь к виртуальному окружению.
8. Статика отдаётся WhiteNoise (настраивать ничего не нужно). Папку `media/`, если возможно, отдавайте веб-сервером хостинга.
9. Бэкапы: включите автоматические бэкапы в панели + раз в неделю скачивайте `db.sqlite3` и `media/`.

> На shared-хостинге сайт работает через WSGI (синхронно) — это нормально, всё работает так же.

---

## Бэкапы

Скрипт `scripts/backup_db.sh` сохраняет базу (PostgreSQL — `pg_dump`, SQLite — безопасная копия) и папку `media/`
в `backups/`, удаляя копии старше 14 дней (`KEEP_DAYS`).

```bash
./scripts/backup_db.sh            # VPS без Docker
./scripts/backup_db.sh --docker   # Docker Compose
```

**Автоматически каждую ночь:**
- VPS без Docker:
  ```bash
  cp deploy/systemd/uc-site-backup.service deploy/systemd/uc-site-backup.timer /etc/systemd/system/
  systemctl daemon-reload && systemctl enable --now uc-site-backup.timer
  ```
- Docker: `crontab -e` и строка
  `30 3 * * * cd /srv/uc-site && ./scripts/backup_db.sh --docker >> backups/backup.log 2>&1`

**Храните копии не только на том же сервере!** Например, раз в неделю скачивайте их:
`scp -r root@IP:/srv/uc-site/backups ./uc-backups` — или настройте выгрузку в облако (rclone, S3 Timeweb/Selectel).

**Восстановление:**
```bash
# PostgreSQL (VPS)
gunzip -c backups/db_2026-11-01_03-30.sql.gz | psql "$DATABASE_URL"
# PostgreSQL (Docker)
gunzip -c backups/db_2026-11-01_03-30.sql.gz | docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
# SQLite
gunzip -c backups/db_2026-11-01_03-30.sqlite3.gz > db.sqlite3
# media
tar -xzf backups/media_2026-11-01_03-30.tar.gz            # VPS
docker compose exec -T web tar -C /app -xzf - < backups/media_2026-11-01_03-30.tar.gz   # Docker
```
Раз в месяц проверяйте, что бэкап реально восстанавливается (на тестовой машине).

---

## Персональные данные: автоудаление заявок (152-ФЗ)

В Политике и Согласии указано: данные заявки хранятся **1 год** с даты заявки (или до отзыва согласия) и уничтожаются
**в течение 30 дней** после этого. Это делает команда `purge_leads` — её нужно запускать **раз в сутки**:

```bash
python manage.py purge_leads --dry-run   # показать, что будет удалено (ничего не меняет)
python manage.py purge_leads             # удалить заявки старше 365 дней, «Спам» — старше 30 дней
python manage.py purge_leads --days 180  # свой срок (тогда поправьте его и в Политике, и в Согласии!)
python manage.py purge_leads --anonymize # не удалять строки, а стереть ПДн (статистика по датам/программам останется)
```
Сроки по умолчанию — переменные `LEAD_RETENTION_DAYS=365` и `LEAD_SPAM_RETENTION_DAYS=30` в `.env`.
Вывод команды содержит только номера и даты заявок (без ПДн) — его можно приложить к акту об уничтожении.

**Docker** — `crontab -e` на сервере:
```
15 4 * * * cd /srv/uc-site && docker compose exec -T web python manage.py purge_leads >> backups/purge.log 2>&1
```

**VPS без Docker** — systemd-таймер (создайте два файла и включите):
```bash
sudo tee /etc/systemd/system/uc-site-purge.service >/dev/null <<'EOF'
[Unit]
Description=Удаление заявок с истёкшим сроком хранения (152-ФЗ)
After=postgresql.service

[Service]
Type=oneshot
User=uc-site
Group=uc-site
WorkingDirectory=/srv/uc-site
EnvironmentFile=/srv/uc-site/.env
ExecStart=/srv/uc-site/.venv/bin/python manage.py purge_leads
EOF

sudo tee /etc/systemd/system/uc-site-purge.timer >/dev/null <<'EOF'
[Unit]
Description=Ежедневное удаление старых заявок

[Timer]
OnCalendar=*-*-* 04:15:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload && sudo systemctl enable --now uc-site-purge.timer
systemctl list-timers | grep uc-site     # проверить, что таймер стоит
journalctl -u uc-site-purge -n 20         # результат последнего запуска
```
**Обычный хостинг** — в панели «Планировщик (cron)»: `cd ~/uc-site && .venv/bin/python manage.py purge_leads` раз в сутки.

Бэкапы хранятся 14 дней (`KEEP_DAYS`), поэтому из резервных копий удалённые данные исчезают сами — укладываемся в 30 дней.
Если клиент **отозвал согласие** — найдите заявку в панели и удалите её (действие «Удалить выбранные заявки»)
или обезличьте («Удалить персональные данные (обезличить)») не позже 30 дней.

**Заголовки безопасности.** Content-Security-Policy и Permissions-Policy ставит сам Django (`core/middleware.py`,
настройки `CSP_DIRECTIVES` в `config/settings.py`): браузер выполняет только скрипты сайта, без CDN и чужих счётчиков.
Подключаете Яндекс Метрику или другой внешний сервис — добавьте его домены в `CSP_DIRECTIVES` **и** опишите его
в Политике ПДн. Для отладки — `CSP_REPORT_ONLY=1` (нарушения только пишутся в консоль браузера).

---

## Безопасность сервера (минимум)

```bash
# Файрвол: только SSH, HTTP, HTTPS
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw enable
# Автоматические обновления безопасности
apt install -y unattended-upgrades && dpkg-reconfigure -plow unattended-upgrades
```
- Вход по SSH-ключу, пароль root отключить (`PasswordAuthentication no` в `/etc/ssh/sshd_config`).
- Docker публикует порты 80/443 в обход ufw — это нормально: снаружи открыт только nginx, база и Django наружу не торчат.
- Пароль от `/admin/` — длинный и уникальный; не используйте логин `admin` в боевом режиме.

## Проверка после запуска

```bash
curl -I https://example.ru/                   # 200, есть strict-transport-security
curl -I http://example.ru/                    # 301 на https
curl -s https://example.ru/robots.txt
curl -s https://example.ru/sitemap.xml | head
```
- Откройте сайт с телефона, отправьте тестовую заявку — пришло уведомление в Telegram/на почту?
- Зайдите в `/admin/`, загрузите PDF в «Документы», проверьте, что он открывается по ссылке на сайте.
- Проверка заголовков: https://securityheaders.com, SSL: https://www.ssllabs.com/ssltest/.

## Если что-то не работает

| Симптом | Где смотреть / что сделать |
|---|---|
| 502 Bad Gateway | Сайт не запущен: `systemctl status uc-site`, `journalctl -u uc-site -n 100` (Docker: `docker compose logs web`) |
| 400 Bad Request | Домен не указан в `ALLOWED_HOSTS` |
| 403 CSRF при отправке формы / входе в админку | Домен с `https://` не указан в `CSRF_TRUSTED_ORIGINS` |
| Бесконечный редирект | `SECURE_SSL_REDIRECT=1`, но прокси не передаёт `X-Forwarded-Proto` |
| Нет стилей | Не выполнен `collectstatic` или неверный путь `alias` в nginx |
| PDF не открываются (404) | Неверный путь `/media/` в nginx или файл не загружен |
| 413 Request Entity Too Large | Увеличьте `client_max_body_size` в nginx |
| Заявки не приходят в Telegram | Проверьте токен/ID чата, бот должен быть добавлен в чат; логи сайта |

