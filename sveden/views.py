"""
Страницы раздела «Сведения об образовательной организации» (/sveden/...).

Состав переменных контекста — CONTRACT.md, п. 5. Во всех подразделах дополнительно:
- section      — словарь текущего подраздела {slug, title, url};
- page_updated — дата последнего изменения данных страницы (date) — выводится
                 как «Дата обновления сведений» (или дата изменения Организации,
                 если на странице ещё нет данных).

Views асинхронные: чтение через async ORM, в контекст — только list.
"""

from asgiref.sync import sync_to_async
from django.db.models import Prefetch
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_safe

from core.context_processors import REQUEST_ORG_ATTR, get_sveden_sections
from core.models import Program

from .models import (
    Department,
    Document,
    EduPlace,
    Facility,
    Founder,
    Manager,
    Organization,
    SvedenField,
    Teacher,
    VacantPlace,
)

# Текст по умолчанию для подраздела «Документы», если предписаний нет.
NO_PRESCRIPTIONS_TEXT = "Предписаний органов, осуществляющих государственный контроль (надзор) в сфере образования, нет"


async def alist(queryset):
    return [obj async for obj in queryset]


def get_section(slug):
    return next(s for s in get_sveden_sections() if s["slug"] == slug)


def compute_page_updated(org, *groups):
    """Самая поздняя updated_at среди объектов страницы → date (в часовом поясе сайта).

    groups — списки объектов (или отдельные объекты/None). Если данных нет,
    берём Organization.updated_at; если нет и её — сегодняшнюю дату.
    """
    stamps = []
    for group in groups:
        items = group if isinstance(group, (list, tuple)) else [group]
        for obj in items:
            value = getattr(obj, "updated_at", None)
            if value:
                stamps.append(value)
    if not stamps and org is not None and org.updated_at:
        stamps.append(org.updated_at)
    if not stamps:
        return timezone.localdate()
    return timezone.localtime(max(stamps)).date()


def docs_for(section):
    return Document.objects.filter(section=section, is_published=True)


def fields_for(page):
    return SvedenField.objects.filter(page=page)


async def render_section(request, slug, context, *data):
    """Добавить section и page_updated и отрендерить sveden/<slug>.html."""
    if "org" in context:
        org = context["org"]
    else:
        org = await Organization.objects.filter(pk=1).afirst()
        context["org"] = org
    setattr(request, REQUEST_ORG_ATTR, org)  # контекст-процессор не будет запрашивать её повторно
    context["section"] = get_section(slug)
    context["page_updated"] = compute_page_updated(org, *data)
    return await sync_to_async(render)(request, f"sveden/{slug}.html", context)


@require_safe
async def index(request):
    org = await Organization.objects.filter(pk=1).afirst()
    setattr(request, REQUEST_ORG_ATTR, org)
    context = {
        "sections": get_sveden_sections(),
        "section": None,
        "page_updated": compute_page_updated(org),
    }
    return await sync_to_async(render)(request, "sveden/index.html", context)


@require_safe
async def common(request):
    founders = await alist(Founder.objects.all())
    places = await alist(EduPlace.objects.all())
    org = await Organization.objects.filter(pk=1).afirst()
    context = {"org": org, "founders": founders, "places": places}
    return await render_section(request, "common", context, org, founders, places)


@require_safe
async def struct(request):
    departments = await alist(Department.objects.all())
    docs = await alist(docs_for("struct"))
    return await render_section(request, "struct", {"departments": departments, "docs": docs}, departments, docs)


@require_safe
async def document(request):
    docs = await alist(docs_for("document"))
    # Текстовые сведения подраздела: «Коллективный договор: отсутствует» (localActCollec) и т.п.
    fields = await alist(fields_for("document"))
    has_prescriptions = any(d.itemprop == "prescriptionDocLink" for d in docs)
    context = {
        "docs": docs,
        "fields": fields,
        "prescriptions_text": "" if has_prescriptions else NO_PRESCRIPTIONS_TEXT,
    }
    return await render_section(request, "document", context, docs, fields)


@require_safe
async def education(request):
    programs = await alist(
        Program.objects.filter(is_published=True).select_related("category").prefetch_related("teachers")
    )
    docs = await alist(docs_for("education"))
    fields = await alist(fields_for("education"))
    context = {"programs": programs, "docs": docs, "fields": fields}
    return await render_section(request, "education", context, programs, docs, fields)


@require_safe
async def edu_standarts(request):
    fields = await alist(fields_for("eduStandarts"))
    docs = await alist(docs_for("eduStandarts"))
    return await render_section(request, "eduStandarts", {"fields": fields, "docs": docs}, fields, docs)


@require_safe
async def managers(request):
    people = await alist(Manager.objects.all())
    head = next((m for m in people if m.role == "head"), None)
    deputies = [m for m in people if m.role == "zam"]
    return await render_section(request, "managers", {"head": head, "deputies": deputies}, people)


@require_safe
async def employees(request):
    # В графе «Участвует в программах» — только опубликованные программы.
    teachers = await alist(
        Teacher.objects.prefetch_related(
            Prefetch("programs", queryset=Program.objects.filter(is_published=True).order_by("order", "title"))
        )
    )
    return await render_section(request, "employees", {"teachers": teachers}, teachers)


@require_safe
async def objects(request):
    facilities = await alist(Facility.objects.all())
    fields = await alist(fields_for("objects"))
    docs = await alist(docs_for("objects"))
    context = {"facilities": facilities, "fields": fields, "docs": docs}
    return await render_section(request, "objects", context, facilities, fields, docs)


@require_safe
async def paid_edu(request):
    docs = await alist(docs_for("paid_edu"))
    programs = await alist(Program.objects.filter(is_published=True).select_related("category"))
    fields = await alist(fields_for("paid_edu"))
    context = {"docs": docs, "programs": programs, "fields": fields}
    return await render_section(request, "paid_edu", context, docs, programs, fields)


@require_safe
async def vacant(request):
    """Вакантные места: строка для КАЖДОЙ опубликованной программы.

    Если для программы ещё не заведена запись VacantPlace (новая программа), показываем
    несохранённый VacantPlace с нулями — п. 6 Требований: сведения по каждой программе.
    """
    programs = await alist(
        Program.objects.filter(is_published=True)
        .select_related("category", "vacant_place")
        .order_by("order", "title")
    )
    vacancies = []
    for program in programs:
        try:
            place = program.vacant_place
        except VacantPlace.DoesNotExist:
            place = VacantPlace(program=program)
        vacancies.append(place)
    saved = [v for v in vacancies if v.pk]
    return await render_section(request, "vacant", {"vacancies": vacancies}, saved)


def _fields_and_docs_view(slug):
    """Фабрика однотипных страниц: только текстовые сведения и документы."""

    @require_safe
    async def view(request):
        fields = await alist(fields_for(slug))
        docs = await alist(docs_for(slug))
        return await render_section(request, slug, {"fields": fields, "docs": docs}, fields, docs)

    view.__name__ = slug
    view.__doc__ = f"Подраздел «{slug}»: текстовые сведения и документы."
    return view


budget = _fields_and_docs_view("budget")
grants = _fields_and_docs_view("grants")
inter = _fields_and_docs_view("inter")
catering = _fields_and_docs_view("catering")
