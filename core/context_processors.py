"""
Контекст-процессор: данные, которые нужны на КАЖДОЙ странице (шапка, меню, подвал,
форма заявки во всплывающем окне). Подключён в settings.TEMPLATES.

Вызывается Django при рендере шаблона. Мы рендерим через sync_to_async(render),
поэтому здесь можно обычное (синхронное) обращение к базе.
"""

from django.conf import settings
from django.urls import reverse

from sveden.models import SECTIONS, Organization

from .forms import LeadForm
from .models import ProgramCategory


def get_sveden_sections():
    """Подразделы «Сведений» в порядке приказа: [{slug, title, url}, ...]."""
    return [
        {"slug": slug, "title": title, "url": reverse(f"sveden:{slug}")}
        for slug, title in SECTIONS
    ]


# Атрибут запроса, в который view может положить уже загруженную Organization,
# чтобы контекст-процессор не запрашивал её из базы второй раз (страницы «Сведений»).
REQUEST_ORG_ATTR = "site_org"
_MISSING = object()


def get_org(request):
    """Organization из запроса (если view её уже загрузил) или из базы."""
    org = getattr(request, REQUEST_ORG_ATTR, _MISSING) if request is not None else _MISSING
    if org is _MISSING:
        org = Organization.load()
    return org


def build_canonical_url(request):
    """Канонический адрес текущей страницы без GET-параметров.

    Если задан SITE_URL (боевой домен) — берём его: за прокси Host может быть внутренним.
    Иначе — адрес из запроса (локальная разработка, демо).
    """
    if request is None:
        return settings.SITE_URL or ""
    if settings.SITE_URL:
        return settings.SITE_URL.rstrip("/") + request.path
    return request.build_absolute_uri(request.path)


def site(request):
    """Общие переменные шаблонов (CONTRACT.md, п. 5)."""
    return {
        "org": get_org(request),  # может быть None — шаблоны это переживают
        "canonical_url": build_canonical_url(request),
        "nav_categories": list(ProgramCategory.objects.all()),
        "sveden_sections": get_sveden_sections(),
        "lead_form": LeadForm(),
        "consent_version": settings.CONSENT_VERSION,
        "site_demo": settings.SITE_DEMO,
    }
