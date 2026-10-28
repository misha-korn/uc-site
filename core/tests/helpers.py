"""
Общие помощники для тестов.

Шаблоны сайта пишет frontend-dev параллельно, поэтому тесты backend не зависят
от них: декоратор `with_stub_templates` подкладывает временную папку с
минимальными шаблонами-заглушками (её DIRS идут ПЕРВЫМИ). Когда настоящие
шаблоны появятся, эти тесты продолжат работать как прежде, а реальный рендер
проверяет отдельный класс RealTemplatesSmokeTests (core/tests/test_pages.py).
"""

import copy
import tempfile
from datetime import date
from pathlib import Path

from django.conf import settings
from django.test import override_settings

from core.models import Program, ProgramCategory
from sveden.models import SECTIONS, Organization

# Одна заглушка на все шаблоны: выводит ключевые переменные контекста,
# csrf-токен и ошибки формы — этого хватает для проверок в тестах.
STUB = (
    "<!doctype html><title>stub {{ request.path }}</title>"
    "{% csrf_token %}"
    "<div id='org'>{{ org.short_name }}</div>"
    "<div id='section'>{{ section.title }}</div>"
    "<div id='updated'>{{ page_updated|date:'d.m.Y' }}</div>"
    "<div id='nonfield'>{{ form.non_field_errors }}</div>"
    "{% for field in form %}<div class='err-{{ field.name }}'>{{ field.errors }}</div>{% endfor %}"
)

STUB_NAMES = [
    "base.html",
    "core/home.html",
    "core/program_list.html",
    "core/program_detail.html",
    "core/contacts.html",
    "core/lead_form_page.html",
    "core/lead_success.html",
    "core/privacy.html",
    "core/consent.html",
    "sveden/index.html",
    "sveden/base_sveden.html",
] + [f"sveden/{slug}.html" for slug, _ in SECTIONS]

_stub_dir = None


def stub_templates_dir():
    """Создать (один раз за прогон) папку с заглушками и вернуть путь."""
    global _stub_dir
    if _stub_dir is None:
        _stub_dir = Path(tempfile.mkdtemp(prefix="uc-stub-templates-"))
        for name in STUB_NAMES:
            path = _stub_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(STUB, encoding="utf-8")
    return _stub_dir


def stub_templates_setting():
    templates = copy.deepcopy(settings.TEMPLATES)
    templates[0]["DIRS"] = [stub_templates_dir()] + list(templates[0]["DIRS"])
    return templates


def with_stub_templates(obj):
    """Декоратор класса/функции теста: рендерить шаблоны-заглушки."""
    return override_settings(TEMPLATES=stub_templates_setting())(obj)


def make_org(**extra):
    values = dict(
        full_name="Автономная некоммерческая организация ДПО «Тест»",
        short_name="АНО ДПО «Тест»",
        reg_date=date(2014, 3, 12),
        address="г. Самара, ул. Тестовая, 1",
        work_time="Пн–Пт 9:00–18:00",
        phones="+7 (846) 000-00-00",
        emails="test@example.com",
        inn="6300000000",
        ogrn="1146300000000",
        license_number="Л035-00000-63/00000000",
        license_issuer="Министерство образования Самарской области",
    )
    values.update(extra)
    return Organization.objects.create(**values)


def make_category(slug="ohrana-truda", **extra):
    values = dict(name="Охрана труда", slug=slug, icon="shield", order=1)
    values.update(extra)
    return ProgramCategory.objects.create(**values)


def make_program(category, slug="ot-a", **extra):
    values = dict(
        category=category,
        title=f"Программа {slug}",
        slug=slug,
        kind="ot",
        hours=16,
        duration="2 дня",
        form="Очная",
        price=2500,
        document_issued="Протокол",
        short="Кратко",
        description="Подробно",
        disciplines="Модуль 1\n\nМодуль 2\n",
        is_popular=True,
    )
    values.update(extra)
    return Program.objects.create(**values)
