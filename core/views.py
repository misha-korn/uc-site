"""
Представления (views) публичной части сайта: главная, программы, контакты, заявка.

Все view асинхронные (сайт работает под ASGI/uvicorn):
- данные читаем async-методами ORM (`aget`, `async for`) и сразу превращаем в list
  (в шаблон QuerySet не передаём — он полез бы в базу уже во время рендера);
- шаблон рендерим через `sync_to_async(render)` — сам движок шаблонов синхронный
  (и контекст-процессор core.context_processors.site внутри тоже).

Имена шаблонов и переменных контекста зафиксированы в CONTRACT.md (п. 4–5).
"""

import ipaddress
import logging

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_safe

from sveden.models import Organization

from .forms import MSG_RATE_LIMIT, LeadForm
from .models import Program, ProgramCategory
from .notify import notify_new_lead

logger = logging.getLogger(__name__)

# Тексты для главной пишет копирайтер в core/content.py. Пока файла нет — пустые списки,
# чтобы сайт и тесты не падали.
try:
    from . import content as _content
except ImportError:  # pragma: no cover — зависит от наличия файла копирайтера
    _content = None


def _content_list(name):
    """Список из core/content.py (или [] если модуля/переменной нет)."""
    value = getattr(_content, name, None) if _content else None
    return list(value) if value else []


async def arender(request, template_name, context=None, status=200):
    """Асинхронная обёртка над render()."""
    return await sync_to_async(render)(request, template_name, context or {}, status=status)


async def alist(queryset):
    """Выполнить запрос асинхронно и вернуть обычный list."""
    return [obj async for obj in queryset]


def published_programs():
    """Опубликованные программы вместе с направлением (без лишних запросов)."""
    return (
        Program.objects.filter(is_published=True)
        .select_related("category")
        .order_by("category__order", "order", "title")
    )


def categories_with_counts():
    """Направления с числом опубликованных программ в атрибуте programs_count.

    После annotate(Count) Django отбрасывает Meta.ordering, поэтому порядок задаём явно.
    """
    return ProgramCategory.objects.annotate(
        programs_count=Count("programs", filter=Q(programs__is_published=True))
    ).order_by("order", "name")


# --- Страницы ----------------------------------------------------------------

@require_safe
async def home(request):
    context = {
        "popular_programs": await alist(published_programs().filter(is_popular=True)),
        "categories": await alist(categories_with_counts()),
        "advantages": _content_list("advantages"),
        "faq": _content_list("faq"),
        "steps": _content_list("steps"),
        "stats": _content_list("stats"),
    }
    return await arender(request, "core/home.html", context)


@require_safe
async def program_list(request):
    """Каталог программ. Фильтр по направлению: ?cat=<slug> (неизвестный slug — показываем все)."""
    categories = await alist(categories_with_counts())
    cat_slug = request.GET.get("cat", "").strip()
    active_category = next((c for c in categories if c.slug == cat_slug), None)

    programs = published_programs()
    if active_category is not None:
        programs = programs.filter(category=active_category)

    context = {
        "categories": categories,
        "programs": await alist(programs),
        "active_category": active_category,
    }
    return await arender(request, "core/program_list.html", context)


@require_safe
async def program_detail(request, slug):
    try:
        program = await published_programs().aget(slug=slug)
    except Program.DoesNotExist:
        raise Http404("Программа не найдена")

    related = await alist(
        published_programs().filter(category_id=program.category_id).exclude(pk=program.pk)[:3]
    )
    context = {
        "program": program,
        "related": related,
        # Форма заявки с уже выбранной программой (перекрывает пустую из контекст-процессора).
        "lead_form": LeadForm(initial={"program": program.pk}),
    }
    return await arender(request, "core/program_detail.html", context)


@require_safe
async def contacts(request):
    return await arender(request, "core/contacts.html")


@require_safe
async def privacy(request):
    return await arender(request, "core/privacy.html")


@require_safe
async def consent(request):
    return await arender(request, "core/consent.html")


@require_safe
async def lead_success(request):
    return await arender(request, "core/lead_success.html")


# --- Заявка ------------------------------------------------------------------

def get_client_ip(request):
    """IP посетителя.

    X-Forwarded-For учитываем ТОЛЬКО если settings.USE_X_FORWARDED_FOR=True (сайт за своим
    nginx). Берём последний адрес цепочки — его дописал наш nginx; первые адреса посетитель
    может подделать.
    """
    candidates = []
    if settings.USE_X_FORWARDED_FOR:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            candidates.append(forwarded.split(",")[-1].strip())
    candidates.append(request.META.get("REMOTE_ADDR", ""))
    for value in candidates:
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            continue
    return None


def mask_ip(ip):
    """IP для журнала без последнего октета (152-ФЗ: в логах не храним полный адрес).

    10.1.2.3 → 10.1.2.x; IPv6 — оставляем первые 3 группы: 2001:db8:1::x. None → «unknown».
    Полный IP сохраняется только в самой заявке — как доказательство согласия.
    """
    if not ip:
        return "unknown"
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return "invalid"
    if addr.version == 4:
        return ".".join(str(addr).split(".")[:3] + ["x"])
    groups = addr.exploded.split(":")[:3]
    return ":".join(g.lstrip("0") or "0" for g in groups) + "::x"


def parse_program_id(value):
    """Номер программы из ?program=: только обычное положительное целое, иначе None.

    str.isdigit() пропускает «²» и другие юникод-цифры, на которых int() падает (была ошибка 500),
    поэтому проверяем через int() и только ASCII-цифры.
    """
    value = (value or "").strip()
    if not (value.isascii() and value.isdigit()):  # отсекаем «²», «1_0», «+5», «-1»
        return None
    try:
        number = int(value)
    except ValueError:
        return None
    return number if number > 0 else None


def _rate_key(ip):
    return f"lead-rate:{ip or 'unknown'}"


async def is_rate_limited(ip):
    """True, если с этого IP уже отправлено LEAD_RATE_LIMIT заявок за последнее окно."""
    count = await cache.aget(_rate_key(ip), 0)
    return count >= settings.LEAD_RATE_LIMIT


async def register_lead_attempt(ip):
    """Увеличить счётчик заявок IP (окно — LEAD_RATE_WINDOW секунд от первой заявки)."""
    key = _rate_key(ip)
    added = await cache.aadd(key, 1, timeout=settings.LEAD_RATE_WINDOW)
    if not added:
        try:
            await cache.aincr(key)
        except ValueError:  # ключ успел истечь между add и incr
            await cache.aset(key, 1, timeout=settings.LEAD_RATE_WINDOW)


@require_http_methods(["GET", "HEAD", "POST"])
async def lead_create(request):
    """Приём заявки.

    GET  — отдельная страница с формой (можно ?program=<pk>), пригодится без JS.
    POST — проверка → сохранение → уведомления → редирект на «Спасибо».
    При ошибках — та же страница core/lead_form_page.html с переменной form.
    """
    template = "core/lead_form_page.html"

    if request.method in ("GET", "HEAD"):
        initial = {}
        program_id = parse_program_id(request.GET.get("program", ""))
        if program_id is not None:
            initial["program"] = program_id
        return await arender(request, template, {"form": LeadForm(initial=initial)})

    form = LeadForm(request.POST)
    is_valid = await sync_to_async(form.is_valid)()  # ModelChoiceField ходит в базу
    ip = get_client_ip(request)

    # Ловушка для ботов: делаем вид, что всё хорошо, но ничего не сохраняем.
    if form.is_bot:
        logger.info("Заявка отклонена: заполнено поле-ловушка (ip=%s)", mask_ip(ip))
        return redirect("core:lead_success")

    if await is_rate_limited(ip):
        logger.warning("Заявка отклонена: превышен лимит с ip=%s", mask_ip(ip))
        org = await Organization.objects.filter(pk=1).afirst()
        phones = f": {org.phones}" if org and org.phones else ""
        form.add_error(None, MSG_RATE_LIMIT.format(phones=phones))
        return await arender(request, template, {"form": form}, status=429)

    if not is_valid:
        return await arender(request, template, {"form": form})

    lead = form.to_lead(ip=ip, consent_version=settings.CONSENT_VERSION, consent_at=timezone.now())
    await lead.asave()
    await register_lead_attempt(ip)
    logger.info("Создана заявка #%s", lead.pk)

    # Ждём уведомления не дольше NOTIFY_TIMEOUT; ошибки внутри логируются и не мешают ответу.
    try:
        await notify_new_lead(lead.pk)
    except Exception:  # noqa: BLE001 — на всякий случай: заявка уже сохранена
        logger.exception("Ошибка при отправке уведомлений о заявке #%s", lead.pk)

    return redirect("core:lead_success")


# --- robots.txt --------------------------------------------------------------

@require_safe
def robots_txt(request):
    """robots.txt. В демо-режиме запрещаем индексацию целиком (данные вымышленные)."""
    lines = ["User-agent: *"]
    if settings.SITE_DEMO:
        lines.append("Disallow: /")
    lines += ["Disallow: /admin/", "Disallow: /zayavka/"]
    base = settings.SITE_URL or request.build_absolute_uri("/").rstrip("/")
    lines.append(f"Sitemap: {base}{reverse('django.contrib.sitemaps.views.sitemap')}")
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")
