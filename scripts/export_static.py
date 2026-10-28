#!/usr/bin/env python3
"""
Статическая демо-копия сайта (CONTRACT.md, п. 12).

Что делает:
  1. Поднимает Django в демо-режиме (SITE_DEMO=1, DEBUG=1) и через django.test.Client
     рендерит все страницы сайта: главная, каталог (+ каждая категория), каждая программа,
     контакты, «спасибо», политика, согласие, раздел «Сведения» и все его подразделы, 404.
  2. Сохраняет каждую страницу как <путь>/index.html (категории — obuchenie/cat-<slug>/index.html).
  3. Переписывает ВСЕ внутренние ссылки (href, src, action, srcset, poster, url(...) в style)
     в относительные с явным index.html — копию можно открыть даже двойным кликом
     по файлу (file://) или выложить на любой статический хостинг в любую подпапку.
  4. Формы: action -> "#", добавляется атрибут data-demo (JS покажет «в демо форма не отправляется»).
     Ссылки на /admin/ превращаются в <span>.
  5. Копирует статику (без файлов Django admin) в dist/static и загруженные файлы в dist/media.
  6. Проверяет, что каждая относительная ссылка в dist ведёт на существующий файл.
     Если есть битые ссылки — печатает отчёт и завершается с кодом 1.

Запуск (из корня проекта):
    python scripts/export_static.py --out dist
    python scripts/export_static.py --out dist --database-url sqlite:////tmp/demo.sqlite3
    python scripts/export_static.py --out dist --database-url sqlite:////tmp/demo.sqlite3 --media-root /tmp/demo-media

Только стандартная библиотека + Django.
"""
from __future__ import annotations

import argparse
import html
import os
import posixpath
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent

# Подразделы «Сведений» (имена URL из CONTRACT.md, п. 4)
SVEDEN_NAMES = [
    "index", "common", "struct", "document", "education", "eduStandarts", "managers",
    "employees", "objects", "paid_edu", "budget", "vacant", "grants", "inter", "catering",
]
CORE_NAMES = ["home", "program_list", "contacts", "lead_success", "privacy", "consent"]

URL_ATTRS = {"href", "src", "action", "poster", "data-src", "data-href", "formaction"}
SRCSET_ATTRS = {"srcset", "data-srcset"}

# Тег целиком с учётом атрибутов в кавычках (внутри кавычек может быть ">").
TAG_RE = re.compile(
    r"<(?P<name>[a-zA-Z][a-zA-Z0-9:-]*)"
    r"(?P<attrs>(?:\s+[^\s\"'>/=]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"'=<>`]+))?)*)"
    r"(?P<tail>\s*/?)>"
)
ATTR_RE = re.compile(
    r"(?P<ws>\s+)(?P<name>[^\s\"'>/=]+)"
    r"(?:(?P<eq>\s*=\s*)(?P<val>\"[^\"]*\"|'[^']*'|[^\s\"'=<>`]+))?"
)
CSS_URL_RE = re.compile(r"url\(\s*(?P<q>['\"]?)(?P<url>[^'\")]+?)(?P=q)\s*\)")
CSS_IMPORT_RE = re.compile(r"@import\s+(?P<q>['\"])(?P<url>[^'\"]+)(?P=q)")
STYLE_BLOCK_RE = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.S | re.I)
ADMIN_LINK_RE = re.compile(r"<a\b(?P<attrs>[^>]*)>(?P<inner>.*?)</a>", re.S | re.I)
HREF_RE = re.compile(r"\bhref\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s\"'=<>`]+)", re.I)
CSRF_INPUT_RE = re.compile(r"<input\b[^>]*\bname\s*=\s*['\"]csrfmiddlewaretoken['\"][^>]*>\s*", re.I)
CLASS_RE = re.compile(r"\bclass\s*=\s*(\"[^\"]*\"|'[^']*')", re.I)
# <link rel="preload" as="font" ...>: при открытии копии с диска (file://) браузер считает шрифт
# «чужим» (CORS) и пишет ошибку в консоль. Сам @font-face в CSS работает и без preload.
LINK_TAG_RE = re.compile(r"<link\b[^>]*>\s*", re.I)

SKIP_SCHEMES = ("http:", "https:", "mailto:", "tel:", "data:", "javascript:", "sms:", "ftp:", "blob:", "about:")


# --------------------------------------------------------------------------- #
#  Чистые функции переписывания ссылок (покрыты юнит-тестами, Django не нужен)
# --------------------------------------------------------------------------- #
class Mapper:
    """Переводит URL сайта в путь файла внутри dist (относительно корня dist)."""

    def __init__(self, static_url: str = "/static/", media_url: str = "/media/"):
        self.static_url = _norm_prefix(static_url)
        self.media_url = _norm_prefix(media_url)

    def page_file(self, path: str, query: str = "") -> str:
        """Путь сохраняемого файла для страницы сайта: '/sveden/common/' -> 'sveden/common/index.html'."""
        cat = _cat_from_query(path, query)
        if cat:
            return f"obuchenie/cat-{cat}/index.html"
        p = unquote(path).lstrip("/")
        if p == "":
            return "index.html"
        if p.endswith("/"):
            return p + "index.html"
        last = p.rsplit("/", 1)[-1]
        if "." in last:  # файл: robots.txt, sitemap.xml, favicon.ico ...
            return p
        return p + "/index.html"

    def target(self, url: str) -> tuple[str, str] | None:
        """
        Для внутренней ссылки вернуть (файл_в_dist, хвост) где хвост — ?query#fragment,
        который надо сохранить. None — ссылку не трогаем.
        """
        if not is_internal_absolute(url):
            return None
        parts = urlsplit(url)
        path, query, frag = parts.path or "/", parts.query, parts.fragment
        tail = ""
        if path.startswith(self.static_url) or path.startswith(self.media_url):
            file = unquote(path).lstrip("/")
        else:
            file = self.page_file(path, query)
            if _cat_from_query(path, query):
                query = ""  # ?cat=... превратился в отдельный файл
        if query:
            tail += "?" + query
        if frag:
            tail += "#" + frag
        return file, tail


def _norm_prefix(prefix: str) -> str:
    prefix = "/" + prefix.strip("/") + "/"
    return prefix.replace("//", "/")


def _cat_from_query(path: str, query: str) -> str | None:
    if path.rstrip("/") != "/obuchenie" or not query:
        return None
    vals = parse_qs(query).get("cat")
    if vals and vals[0]:
        return re.sub(r"[^\w-]", "", vals[0])
    return None


def is_internal_absolute(url: str) -> bool:
    """'/x/' — внутренняя абсолютная ссылка. '//cdn', 'http:', '#a', 'mailto:' — нет."""
    url = url.strip()
    return url.startswith("/") and not url.startswith("//")


def relpath(target_file: str, current_file: str) -> str:
    """Относительный путь от страницы current_file до файла target_file (оба — от корня dist)."""
    start = posixpath.dirname(current_file) or "."
    return posixpath.relpath(target_file, start)


def rewrite_url(url: str, current_file: str, mapper: Mapper, page_path: str = "") -> str:
    stripped = url.strip()
    if page_path and stripped.startswith("?"):
        stripped = page_path + stripped  # href="?cat=x" на странице /obuchenie/
    t = mapper.target(stripped)
    if t is None:
        return url
    file, tail = t
    return relpath(file, current_file) + tail


def rewrite_srcset(value: str, current_file: str, mapper: Mapper) -> str:
    out = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        bits = item.split(None, 1)
        bits[0] = rewrite_url(bits[0], current_file, mapper)
        out.append(" ".join(bits))
    return ", ".join(out)


def rewrite_css(css: str, current_file: str, mapper: Mapper) -> str:
    def sub(m: re.Match) -> str:
        q = m.group("q")
        return f"url({q}{rewrite_url(m.group('url'), current_file, mapper)}{q})"

    def sub_import(m: re.Match) -> str:
        q = m.group("q")
        return f"@import {q}{rewrite_url(m.group('url'), current_file, mapper)}{q}"

    css = CSS_URL_RE.sub(sub, css)
    return CSS_IMPORT_RE.sub(sub_import, css)


def _unquote_attr(raw: str) -> str:
    if raw[:1] in "\"'" and raw[-1:] == raw[:1]:
        raw = raw[1:-1]
    return html.unescape(raw)


def _quote_attr(value: str) -> str:
    return '"' + value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;") + '"'


def replace_admin_links(page: str, is_admin) -> str:
    def sub(m: re.Match) -> str:
        href = HREF_RE.search(m.group("attrs") or "")
        if not href or not is_admin(_unquote_attr(href.group(1))):
            return m.group(0)
        cls = CLASS_RE.search(m.group("attrs") or "")
        cls_attr = f" class={cls.group(1)}" if cls else ""
        return f"<span{cls_attr}>{m.group('inner')}</span>"

    return ADMIN_LINK_RE.sub(sub, page)


def remove_font_preloads(page: str) -> str:
    """Убрать <link rel="preload" as="font" ...> (порядок атрибутов и кавычки — любые)."""

    def sub(m: re.Match) -> str:
        tag = m.group(0)[len("<link"):]
        attrs = {a.group("name").lower(): _unquote_attr(a.group("val") or "") for a in ATTR_RE.finditer(tag)}
        rels = attrs.get("rel", "").lower().split()
        if "preload" in rels and attrs.get("as", "").lower() == "font":
            return ""
        return m.group(0)

    return LINK_TAG_RE.sub(sub, page)


def _is_admin_url(url: str) -> bool:
    u = url.strip()
    if not is_internal_absolute(u):
        return False
    return urlsplit(u).path.rstrip("/") == "/admin" or urlsplit(u).path.startswith("/admin/")


def rewrite_html(page: str, current_file: str, mapper: Mapper, site_url: str = "", page_path: str = "") -> str:
    """Переписать все внутренние ссылки страницы в относительные + демо-правки форм и админки."""
    # 1. Абсолютные ссылки на тестовый хост -> SITE_URL (canonical, og:url должны остаться абсолютными)
    if site_url:
        page = re.sub(r"https?://testserver(?=[/\"'?#\s<]|$)", site_url.rstrip("/"), page)
    # 2. Ссылки на админку — убрать
    page = replace_admin_links(page, _is_admin_url)
    # 3. CSRF-токены в статике бессмысленны
    page = CSRF_INPUT_RE.sub("", page)
    # 3a. preload шрифтов ломается на file:// (CORS) — убираем
    page = remove_font_preloads(page)

    # 4. Атрибуты всех тегов
    def tag_sub(m: re.Match) -> str:
        name = m.group("name").lower()
        attrs = m.group("attrs") or ""
        has_action = False

        def attr_sub(a: re.Match) -> str:
            nonlocal has_action
            aname = a.group("name").lower()
            raw = a.group("val")
            if raw is None:
                return a.group(0)
            value = _unquote_attr(raw)
            if name == "form" and aname == "action":
                has_action = True
                new = "#"
            elif aname in URL_ATTRS:
                new = rewrite_url(value, current_file, mapper, page_path)
            elif aname in SRCSET_ATTRS:
                new = rewrite_srcset(value, current_file, mapper)
            elif aname == "style" and "url(" in value:
                new = rewrite_css(value, current_file, mapper)
            else:
                return a.group(0)
            if new == value:
                return a.group(0)
            return f"{a.group('ws')}{a.group('name')}{a.group('eq')}{_quote_attr(new)}"

        new_attrs = ATTR_RE.sub(attr_sub, attrs)
        if name == "form":
            if not has_action:
                new_attrs += ' action="#"'
            if not re.search(r"\sdata-demo(\s|=|$)", new_attrs):
                new_attrs += " data-demo"
        return f"<{m.group('name')}{new_attrs}{m.group('tail')}>"

    page = TAG_RE.sub(tag_sub, page)

    # 5. <style> блоки
    page = STYLE_BLOCK_RE.sub(
        lambda m: m.group(1) + rewrite_css(m.group(2), current_file, mapper) + m.group(3), page
    )
    return page


# --------------------------------------------------------------------------- #
#  Проверка ссылок в готовом dist
# --------------------------------------------------------------------------- #
def extract_links(text: str, is_css: bool, navigable_only: bool = False) -> list[str]:
    links: list[str] = []
    if not is_css:
        for m in TAG_RE.finditer(text):
            if navigable_only and m.group("name").lower() != "a":
                continue
            for a in ATTR_RE.finditer(m.group("attrs") or ""):
                aname = a.group("name").lower()
                if a.group("val") is None:
                    continue
                if navigable_only and aname != "href":
                    continue
                val = _unquote_attr(a.group("val"))
                if aname in URL_ATTRS:
                    links.append(val)
                elif aname in SRCSET_ATTRS:
                    links += [p.strip().split(None, 1)[0] for p in val.split(",") if p.strip()]
                elif aname == "style":
                    links += [u.group("url") for u in CSS_URL_RE.finditer(val)]
        for sm in STYLE_BLOCK_RE.finditer(text):
            links += [u.group("url") for u in CSS_URL_RE.finditer(sm.group(2))]
    else:
        links += [u.group("url") for u in CSS_URL_RE.finditer(text)]
        links += [u.group("url") for u in CSS_IMPORT_RE.finditer(text)]
    return links


def check_dist(out: Path) -> list[tuple[str, str, str]]:
    """Вернуть список битых ссылок: (файл, ссылка, причина)."""
    broken: list[tuple[str, str, str]] = []
    files = [p for p in out.rglob("*") if p.suffix.lower() in (".html", ".css") and p.is_file()]
    for f in files:
        rel_f = f.relative_to(out).as_posix()
        text = f.read_text(encoding="utf-8", errors="replace")
        for link in extract_links(text, f.suffix.lower() == ".css"):
            link = link.strip()
            if not link or link.startswith("#") or link.lower().startswith(SKIP_SCHEMES) or link.startswith("//"):
                continue
            if link.startswith("/"):
                broken.append((rel_f, link, "абсолютная внутренняя ссылка не переписана"))
                continue
            path = unquote(urlsplit(link).path)
            if not path:
                continue
            target = (f.parent / path).resolve()
            try:
                target.relative_to(out.resolve())
            except ValueError:
                broken.append((rel_f, link, "ведёт за пределы dist"))
                continue
            if target.is_dir():
                broken.append((rel_f, link, "ведёт на папку, а не на файл"))
            elif not target.exists():
                broken.append((rel_f, link, "файл не существует"))
    return broken


# --------------------------------------------------------------------------- #
#  Работа с Django
# --------------------------------------------------------------------------- #
def setup_django(database_url: str | None, media_root: str | None = None) -> None:
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ["SITE_DEMO"] = "1"
    os.environ["DEBUG"] = "1"
    os.environ["SECURE_SSL_REDIRECT"] = "0"
    if database_url:
        os.environ["DATABASE_URL"] = database_url
    if media_root:
        # Брать загруженные файлы (PDF) из другой папки, напр. после seed_demo во временную.
        os.environ["MEDIA_ROOT"] = str(Path(media_root).resolve())
    import django

    django.setup()
    from django.conf import settings

    hosts = list(settings.ALLOWED_HOSTS)
    for h in ("testserver", "localhost", "127.0.0.1"):
        if h not in hosts and "*" not in hosts:
            hosts.append(h)
    settings.ALLOWED_HOSTS = hosts


def collect_page_urls() -> list[str]:
    """Список URL всех страниц сайта (импорт моделей — только после django.setup())."""
    from django.urls import NoReverseMatch, reverse

    urls: list[str] = []

    def add(name: str, *args) -> None:
        try:
            u = reverse(name, args=args)
        except NoReverseMatch:
            print(f"  ! URL '{name}' не найден — пропускаю", file=sys.stderr)
            return
        if u not in urls:
            urls.append(u)

    for n in CORE_NAMES:
        add(f"core:{n}")
    for n in SVEDEN_NAMES:
        add(f"sveden:{n}")

    try:
        from core.models import Program, ProgramCategory

        base = reverse("core:program_list")
        for cat in ProgramCategory.objects.order_by("order", "pk"):
            urls.append(f"{base}?cat={cat.slug}")
        qs = Program.objects.all()
        if hasattr(Program, "is_published"):
            qs = qs.filter(is_published=True)
        for p in qs.order_by("pk"):
            u = p.get_absolute_url()
            if u not in urls:
                urls.append(u)
    except Exception as exc:  # noqa: BLE001 — модели могут быть ещё не готовы
        print(f"  ! Не удалось получить программы/категории: {exc}", file=sys.stderr)
    return urls


def render_404() -> str | None:
    """Рендер собственного шаблона 404.html (в DEBUG Django показал бы техническую страницу)."""
    from django.contrib.auth.models import AnonymousUser
    from django.template import TemplateDoesNotExist, loader
    from django.test import RequestFactory

    try:
        tpl = loader.get_template("404.html")
    except TemplateDoesNotExist:
        print("  ! Шаблон 404.html не найден — 404 не экспортирована", file=sys.stderr)
        return None
    req = RequestFactory().get("/404/")
    req.user = AnonymousUser()
    return tpl.render({"request_path": "/404/", "exception": "Not found"}, req)


def copy_static(out: Path) -> int:
    """Скопировать статику проекта (без Django admin) в dist/static. Возвращает число файлов."""
    import django.contrib.admin as admin_pkg
    from django.contrib.staticfiles import finders

    admin_dir = Path(admin_pkg.__file__).resolve().parent
    dest_root = out / "static"
    count, seen = 0, set()
    for finder in finders.get_finders():
        for path, storage in finder.list(["CVS", ".*", "*~"]):
            location = Path(getattr(storage, "location", "") or ".").resolve()
            if admin_dir in location.parents or location == admin_dir:
                continue
            prefix = getattr(storage, "prefix", None)
            rel = f"{prefix}/{path}" if prefix else path
            if rel in seen:
                continue
            seen.add(rel)
            dest = dest_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with storage.open(path) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    return count


def copy_media(out: Path) -> int:
    from django.conf import settings

    media_root = Path(str(settings.MEDIA_ROOT or ""))
    if not settings.MEDIA_ROOT or not media_root.is_dir():
        return 0
    dest = out / "media"
    shutil.copytree(media_root, dest, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".gitkeep", ".*"))
    return sum(1 for p in dest.rglob("*") if p.is_file())


def export(out: Path, database_url: str | None, site_url_arg: str | None, media_root: str | None = None) -> int:
    setup_django(database_url, media_root)
    from django.conf import settings
    from django.test import Client

    site_url = (site_url_arg or getattr(settings, "SITE_URL", "") or os.environ.get("SITE_URL")
                or "http://localhost:8000").rstrip("/")
    mapper = Mapper(settings.STATIC_URL or "/static/", settings.MEDIA_URL or "/media/")

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    import logging

    # Трейсбеки ошибок страниц не печатаем — ниже будет собственный краткий отчёт
    for name in ("django.request", "django.server"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    client = Client(raise_request_exception=True)
    queue = collect_page_urls()
    required = set(queue)  # обязательные страницы; найденные по ссылкам — только предупреждения
    done: set[str] = set()
    pages, errors, warnings = 0, [], []
    print(f"Экспорт в {out} (SITE_URL={site_url})")

    while queue:
        url = queue.pop(0)
        if url in done:
            continue
        done.add(url)
        try:
            resp = client.get(url)
        except Exception as exc:  # noqa: BLE001 — ошибка шаблона/вью: фиксируем и идём дальше
            (errors if url in required else warnings).append(f"{url} -> {exc.__class__.__name__}: {exc}")
            continue
        ctype = resp.get("Content-Type", "")
        if resp.status_code != 200 or "text/html" not in ctype:
            (errors if url in required else warnings).append(f"{url} -> HTTP {resp.status_code} ({ctype})")
            continue
        parts = urlsplit(url)
        file = mapper.page_file(parts.path, parts.query)
        text = resp.content.decode(resp.charset or "utf-8")
        # Дообход: внутренние страницы, на которые есть ссылки, но которых нет в списке
        for link in extract_links(text, False, navigable_only=True):
            if link.strip().startswith("?"):
                link = parts.path + link.strip()
            if not is_internal_absolute(link) or _is_admin_url(link):
                continue
            lp = urlsplit(link)
            if lp.path.startswith((mapper.static_url, mapper.media_url)):
                continue
            last = lp.path.rstrip("/").rsplit("/", 1)[-1]
            if "." in last:  # robots.txt, sitemap.xml и т.п. — ниже отдельно
                continue
            cand = lp.path + (f"?{lp.query}" if _cat_from_query(lp.path, lp.query) else "")
            if cand not in done and cand not in queue:
                queue.append(cand)
        html_out = rewrite_html(text, file, mapper, site_url, parts.path)
        dest = out / file
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html_out, encoding="utf-8")
        pages += 1
        print(f"  {url:<45} -> {file}")

    try:
        page404 = render_404()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"404.html -> {exc.__class__.__name__}: {exc}")
        page404 = None
    if page404:
        (out / "404.html").write_text(rewrite_html(page404, "404.html", mapper, site_url), encoding="utf-8")
        pages += 1
        print(f"  {'(404)':<45} -> 404.html")

    # sitemap.xml — как есть (абсолютные ссылки на SITE_URL); robots.txt — демо-копию не индексируем
    try:
        resp = client.get("/sitemap.xml")
        if resp.status_code == 200:
            xml = re.sub(r"https?://testserver", site_url, resp.content.decode("utf-8"))
            (out / "sitemap.xml").write_text(xml, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"  ! sitemap.xml не экспортирован: {exc}", file=sys.stderr)
    (out / "robots.txt").write_text("# Демо-копия: данные вымышленные, не индексировать\n"
                                    "User-agent: *\nDisallow: /\n", encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")  # для GitHub Pages

    n_static = copy_static(out)
    n_media = copy_media(out)
    for css in (out / "static").rglob("*.css"):
        rel = css.relative_to(out).as_posix()
        txt = css.read_text(encoding="utf-8", errors="replace")
        new = rewrite_css(txt, rel, mapper)
        if new != txt:
            css.write_text(new, encoding="utf-8")

    print(f"\nСтраниц: {pages}, файлов статики: {n_static}, файлов media: {n_media}")
    if warnings:
        print("\nПредупреждение: страницы по ссылкам не отрендерились (ссылки на них будут битыми):", file=sys.stderr)
        for w in warnings:
            print("  " + w, file=sys.stderr)
    if errors:
        print("\nНе отрендерились обязательные страницы:", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)

    broken = check_dist(out)
    if broken:
        print(f"\nБитые ссылки: {len(broken)}", file=sys.stderr)
        for f, link, why in broken[:200]:
            print(f"  {f}: {link}  — {why}", file=sys.stderr)
        if len(broken) > 200:
            print(f"  ... и ещё {len(broken) - 200}", file=sys.stderr)
    else:
        print("Проверка ссылок: битых нет.")
    print(f"Готово. Откройте {out / 'index.html'} в браузере.")
    return 1 if (broken or errors) else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Статическая демо-копия сайта (HTML + static + media).")
    ap.add_argument("--out", default="dist", help="папка результата (по умолчанию dist; будет очищена)")
    ap.add_argument("--database-url", default=None, help="БД-источник, напр. sqlite:////tmp/demo.sqlite3")
    ap.add_argument("--site-url", default=None, help="адрес для canonical/og:url (по умолчанию SITE_URL)")
    ap.add_argument("--media-root", default=None,
                    help="папка с загруженными файлами (по умолчанию env MEDIA_ROOT или media/ проекта)")
    ap.add_argument("--check-only", action="store_true", help="только проверить ссылки в уже готовой папке")
    args = ap.parse_args(argv)

    out = Path(args.out)
    if not out.is_absolute():
        out = (Path.cwd() / out).resolve()
    if out == ROOT or out in ROOT.parents:
        ap.error("--out не может быть корнем проекта")

    if args.check_only:
        broken = check_dist(out)
        for f, link, why in broken:
            print(f"{f}: {link}  — {why}")
        print(f"Битых ссылок: {len(broken)}")
        return 1 if broken else 0
    return export(out, args.database_url, args.site_url, args.media_root)


if __name__ == "__main__":
    sys.exit(main())
