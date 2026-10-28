"""Шаблонные теги оформления.

`{% load ui %}` → `{% icon "fire" %}` / `{% icon c.icon cls="extra" %}` — inline SVG-иконка.
Заменяет `{% include "core/_icon.html" with name=... %}` (include на каждую иконку — ~50 рендеров
подшаблона на страницу). Набор иконок фиксирован: неизвестное имя → нейтральный кружок,
пользовательский ввод в разметку не попадает (имя попадает в class только если оно есть в словаре).
"""
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

# Контуры 24×24, stroke = currentColor. Ключи направлений (ProgramCategory.icon):
# shield, fire, helmet, cross, bolt, crane, weld, factory. Остальные — служебные.
PATHS = {
    "shield": (
        '<path d="M12 2.8 4.5 5.6v5.9c0 4.6 3.1 8.2 7.5 9.7 4.4-1.5 7.5-5.1 7.5-9.7V5.6L12 2.8Z"/><path d="M12 7.5v9M7.5 12h9"/>'
    ),
    "fire": (
        '<path d="M12 21.2c-3.9 0-6.8-2.7-6.8-6.4 0-3.3 2.3-5.4 3.6-7.3.4 1.6 1.2 2.7 2.3 3.2-.3-3 1-5.9 3.4-7.9.2 3.2 2 5 3.3 6.9 1 1.4 1.5 3 1.5 4.9 0 3.9-3.3 6.6-7.3 6.6Z"/><path d="M12 21.2c-1.7 0-3-1.2-3-2.9 0-1.6 1.2-2.6 2-3.8.4 1 1 1.4 1.7 1.6.1-.8.5-1.6 1.1-2.2.8 1.2 1.3 2.2 1.3 3.5 0 2.2-1.4 3.8-3.1 3.8Z"/>'
    ),
    "helmet": (
        '<path d="M3 17.5h18"/><path d="M4.5 17.5v-2.2A7.5 7.5 0 0 1 12 7.8a7.5 7.5 0 0 1 7.5 7.5v2.2"/><path d="M10 8V5.4c0-.5.4-.9.9-.9h2.2c.5 0 .9.4.9.9V8"/><path d="M8 11.5c-.9.9-1.4 2.2-1.5 3.5M16 11.5c.9.9 1.4 2.2 1.5 3.5"/><path d="M3 17.5c0 1.1.9 2 2 2h14a2 2 0 0 0 2-2"/>'
    ),
    "cross": (
        '<rect x="3.2" y="3.2" width="17.6" height="17.6" rx="3"/><path d="M10 7h4v3h3v4h-3v3h-4v-3H7v-4h3V7Z"/>'
    ),
    "bolt": (
        '<path d="M13.2 2.5 5.5 13.2h5.7l-1.4 8.3 7.7-10.7h-5.7l1.4-8.3Z"/>'
    ),
    "crane": (
        '<path d="M5 21V3.5M5 4.5h15M5 8.5 9.5 4.5M17 4.5v6"/><path d="M15.2 13.5h3.6l-.9 2.6h-1.8l-.9-2.6Z"/><path d="M17 10.5v3"/><path d="M3 21h5"/><path d="M5 12.5h2.5M5 16.5h2.5"/>'
    ),
    "weld": (
        '<path d="M3.5 20.5h17"/><path d="M6 17.5h12"/><path d="M14.5 3.5 9 12"/><path d="M8 13.5l1-1.5 1.6 1-1 1.5L8 13.5Z"/><path d="M5.5 9.5 4 8.6M7.4 7.7 7 6M10 9.7l1.7-.3M5 12.3l-1.6.5"/>'
    ),
    "factory": (
        '<path d="M3 20.5V10l5 3V10l5 3V10l5 3V4.5h3v16H3Z"/><path d="M7 17h2M11.5 17h2M16 17h2"/>'
    ),
    "phone": (
        '<path d="M5.3 3.5h3l1.6 4.2-2 1.3a11 11 0 0 0 5.1 5.1l1.3-2 4.2 1.6v3c0 1-.8 1.8-1.8 1.8C9.9 18.5 5.5 14.1 3.5 5.3c0-1 .8-1.8 1.8-1.8Z"/>'
    ),
    "mail": (
        '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3.8 6.2 8.2 6.3 8.2-6.3"/>'
    ),
    "pin": (
        '<path d="M12 21s-6.5-6.1-6.5-11.2a6.5 6.5 0 0 1 13 0C18.5 14.9 12 21 12 21Z"/><circle cx="12" cy="9.8" r="2.4"/>'
    ),
    "clock": (
        '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'
    ),
    "pdf": (
        '<path d="M14 3H6.5c-.8 0-1.5.7-1.5 1.5v15c0 .8.7 1.5 1.5 1.5h11c.8 0 1.5-.7 1.5-1.5V8l-5-5Z"/><path d="M14 3v5h5"/><path d="M8.5 13.5h7M8.5 16.5h5"/>'
    ),
    "sign": (
        '<path d="M4 17.5c2.2-.2 3-3.9 4.4-3.9 1.3 0 .4 3.4 1.8 3.4 1.2 0 1.5-2 2.6-2 .9 0 1 1.3 1.9 1.3"/><path d="M14.5 6.5 17.5 9.5M19.5 4.5a2.1 2.1 0 0 1 0 3L11 16l-3.5 1 1-3.5L17 4.5a2.1 2.1 0 0 1 2.5 0Z"/><path d="M3.5 20.5h17"/>'
    ),
    "check": (
        '<path d="m4.5 12.5 4.5 4.5L19.5 6.5"/>'
    ),
    "chevron": (
        '<path d="m9 5 7 7-7 7"/>'
    ),
    "eye": (
        '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/>'
    ),
    "menu": (
        '<path d="M4 7h16M4 12h16M4 17h16"/>'
    ),
    "close": (
        '<path d="M6 6l12 12M18 6 6 18"/>'
    ),
    "doc": (
        '<path d="M7 3.5h7l4 4V20a.5.5 0 0 1-.5.5h-10.5a.5.5 0 0 1-.5-.5V4a.5.5 0 0 1 .5-.5Z"/><path d="M9 11h6M9 14h6M9 17h4"/>'
    ),
    "users": (
        '<circle cx="9" cy="8" r="3.2"/><path d="M3 19.5c.6-3.3 3-5.2 6-5.2s5.4 1.9 6 5.2"/><path d="M15.5 4.9a3.2 3.2 0 0 1 0 6.2M17.5 14.6c1.9.6 3.1 2.3 3.5 4.9"/>'
    ),
    "truck": (
        '<path d="M2.5 6.5h11v10h-11z"/><path d="M13.5 9.5h4l3 3.5v3.5h-7"/><circle cx="6.5" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/>'
    ),
    "info": (
        '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.8v.2"/>'
    ),
}
DEFAULT_PATH = '<circle cx="12" cy="12" r="8.5"/>'

_SVG_OPEN = (
    '<svg class="icon icon--{name}{cls}" viewBox="0 0 24 24" width="24" height="24" fill="none" '
    'stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true" focusable="false">'
)

# Готовые строки SVG без доп. класса — собираются один раз при импорте.
_CACHE = {
    name: _SVG_OPEN.format(name=name, cls="") + path + "</svg>" for name, path in PATHS.items()
}


@register.simple_tag
def icon(name, cls=""):
    """Inline SVG-иконка из фиксированного набора (декоративная, aria-hidden)."""
    name = str(name or "")
    if name in PATHS:
        if not cls:
            return mark_safe(_CACHE[name])
        return mark_safe(_SVG_OPEN.format(name=name, cls=" " + escape(cls)) + PATHS[name] + "</svg>")
    extra = " " + escape(cls) if cls else ""
    return mark_safe(_SVG_OPEN.format(name="default", cls=extra) + DEFAULT_PATH + "</svg>")


# --- Фильтры для подразделов «Сведений» -----------------------------------------------------

def _props(arg):
    return {p.strip() for p in str(arg or "").split(",") if p.strip()}


@register.filter
def by_prop(items, props):
    """Элементы (SvedenField/Document) с itemprop из списка: `fields|by_prop:"finPost,finRas"`."""
    wanted = _props(props)
    return [x for x in (items or []) if getattr(x, "itemprop", "") in wanted]


@register.filter
def exclude_props(items, props):
    """Элементы, у которых itemprop НЕ из списка: `fields|exclude_props:"internationalDog"`."""
    skip = _props(props)
    return [x for x in (items or []) if getattr(x, "itemprop", "") not in skip]


@register.filter
def cols(value, count):
    """Значение «a; b; c» → список ровно из count ячеек (пустые → «Отсутствует»).

    Лишние части склеиваются в последнюю ячейку, чтобы ничего не потерять.
    """
    count = max(int(count or 1), 1)
    parts = [p.strip() for p in str(value or "").split(";")]
    if len(parts) > count:
        parts = parts[: count - 1] + ["; ".join(parts[count - 1:])]
    parts += [""] * (count - len(parts))
    return [p or "Отсутствует" for p in parts]


# Все виды мест осуществления образовательной деятельности (п. 3.2 метод. рекомендаций).
# Порядок вывода и подписи по умолчанию; подписи из модели EduPlace имеют приоритет.
PLACE_KINDS = [
    ("dop", "addressPlaceDop", "Место реализации дополнительных профессиональных программ"),
    ("oppo", "addressPlaceOppo", "Место реализации программ профессионального обучения"),
    ("prac", "addressPlacePrac", "Место проведения практики"),
    ("podg", "addressPlacePodg", "Место проведения практической подготовки обучающихся"),
    ("gia", "addressPlaceGia", "Место проведения итоговой аттестации"),
    ("set", "addressPlaceSet", "Место реализации программ в сетевой форме"),
]


@register.filter
def missing_place_kinds(places):
    """Виды мест, по которым нет ни одной записи: [{"itemprop", "label"}, ...] — для строк «Отсутствует»."""
    present = {getattr(p, "itemprop", "") for p in (places or [])}
    labels = {}
    try:
        from sveden.models import EduPlace

        labels = dict(EduPlace.KIND_CHOICES)
    except Exception:  # pragma: no cover — модель всегда есть, но фильтр не должен ронять страницу
        pass
    return [
        {"itemprop": prop, "label": labels.get(kind, label)}
        for kind, prop, label in PLACE_KINDS
        if prop not in present
    ]


@register.filter
def describedby(bound_field, element_id):
    """Отрисовать поле формы с aria-describedby (подсказка под полем): `{{ form.comment|describedby:"comment-hint" }}`."""
    try:
        existing = bound_field.field.widget.attrs.get("aria-describedby", "")
        ids = " ".join(x for x in (existing, str(element_id)) if x)
        if bound_field.errors:
            ids = f"{ids} {bound_field.auto_id}_error"
        return bound_field.as_widget(attrs={"aria-describedby": ids})
    except AttributeError:  # не поле формы — отдаём как есть
        return bound_field
