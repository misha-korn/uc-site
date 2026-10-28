"""
Панель заказчика: программы, направления и заявки.

Заявки содержат персональные данные (152-ФЗ):
- IP и данные о согласии только для чтения (это доказательство согласия);
- действие «Экспорт в CSV» — для передачи в работу;
- действие «Обезличить» — стирает ПДн, когда цель обработки достигнута.
"""

import csv

from django.contrib import admin, messages
from django.db.models import Count
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from sveden.models import VacantPlace

from .models import Lead, Program, ProgramCategory


# Символы, с которых Excel/LibreOffice начинают формулу. Ячейку с таким началом
# экранируем апострофом — иначе «=HYPERLINK(...)» из формы заявки выполнится у менеджера (CSV-инъекция).
CSV_FORMULA_CHARS = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value):
    """Значение для CSV: None → '', строку-«формулу» — с префиксом '."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    if value.startswith(CSV_FORMULA_CHARS):
        return "'" + value
    return value


class ProgramInline(admin.TabularInline):
    model = Program
    fields = ("title", "kind", "hours", "price", "is_published", "order")
    show_change_link = True
    extra = 0


@admin.register(ProgramCategory)
class ProgramCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon", "order", "programs_total")
    list_editable = ("order",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProgramInline]

    def get_queryset(self, request):
        # Число программ — одним запросом (annotate), а не отдельным COUNT на каждую строку.
        return super().get_queryset(request).annotate(_programs_total=Count("programs"))

    @admin.display(description="программ", ordering="_programs_total")
    def programs_total(self, obj):
        return obj._programs_total


class VacantPlaceInline(admin.TabularInline):
    """Вакантные места прямо на странице программы (выводятся в /sveden/vacant/)."""

    model = VacantPlace
    extra = 0
    max_num = 1
    verbose_name = "вакантные места"
    verbose_name_plural = "вакантные места (раздел «Сведения → Вакантные места»; нет записи — на сайте нули)"


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "kind", "hours", "price", "is_popular", "is_published", "order")
    list_display_links = ("title",)
    list_editable = ("price", "is_popular", "is_published", "order")
    list_filter = ("category", "kind", "is_published", "is_popular")
    search_fields = ("title", "code", "short")
    prepopulated_fields = {"slug": ("title",)}
    list_select_related = ("category",)
    inlines = [VacantPlaceInline]
    save_on_top = True
    fieldsets = (
        ("Основное", {"fields": ("category", "title", "slug", "kind", "code", "is_published", "is_popular", "order")}),
        ("Условия обучения", {"fields": ("hours", "duration", "form", "price", "document_issued", "language")}),
        ("Описание", {"fields": ("short", "description", "audience", "disciplines", "practice")}),
        (
            "Документы программы (для раздела «Сведения → Образование»)",
            {
                "fields": ("op_file", "plan_file", "schedule_file", "rpd_file", "methodology_file"),
                "description": "Загружайте PDF с текстовым слоем (не сканы без распознавания).",
            },
        ),
    )

    def view_on_site(self, obj):
        return obj.get_absolute_url()


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("number", "created_at", "status_badge", "name", "phone", "program", "organization", "listeners")
    list_display_links = ("number", "name")
    list_filter = ("status", "need_invoice", ("created_at", admin.DateFieldListFilter), "program__category")
    search_fields = ("name", "phone", "email", "organization", "comment")
    date_hierarchy = "created_at"
    list_select_related = ("program",)
    list_per_page = 50
    readonly_fields = ("created_at", "ip", "consent", "consent_version", "consent_at")
    autocomplete_fields = ("program",)
    actions = ("mark_in_work", "mark_done", "mark_spam", "export_csv", "anonymize")
    fieldsets = (
        ("Обработка", {"fields": ("status", "staff_note")}),
        (
            "Данные заявки",
            {"fields": ("name", "phone", "email", "organization", "program", "listeners", "need_invoice", "comment")},
        ),
        ("Согласие на обработку ПДн (только чтение)", {"fields": ("consent", "consent_version", "consent_at", "ip", "created_at")}),
    )

    STATUS_COLORS = {"new": "#d93025", "work": "#e37400", "done": "#188038", "spam": "#80868b"}

    @admin.display(description="№", ordering="id")
    def number(self, obj):
        return f"#{obj.pk}"

    @admin.display(description="статус", ordering="status")
    def status_badge(self, obj):
        color = self.STATUS_COLORS.get(obj.status, "#555")
        return format_html('<b style="color:{}">{}</b>', color, obj.get_status_display())

    def has_add_permission(self, request):
        # Заявки создаются только посетителями сайта (с согласием на обработку ПДн).
        return False

    @admin.action(description="Отметить «В работе»")
    def mark_in_work(self, request, queryset):
        updated = queryset.update(status="work")
        self.message_user(request, f"Обновлено заявок: {updated}")

    @admin.action(description="Отметить «Обработана»")
    def mark_done(self, request, queryset):
        updated = queryset.update(status="done")
        self.message_user(request, f"Обновлено заявок: {updated}")

    @admin.action(description="Отметить как спам")
    def mark_spam(self, request, queryset):
        updated = queryset.update(status="spam")
        self.message_user(request, f"Обновлено заявок: {updated}")

    @admin.action(description="Экспорт в CSV (Excel)")
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        stamp = timezone.localtime().strftime("%Y-%m-%d_%H-%M")
        response["Content-Disposition"] = f'attachment; filename="zayavki_{stamp}.csv"'
        response.write("﻿")  # BOM — чтобы Excel открыл кириллицу без «кракозябр»
        writer = csv.writer(response, delimiter=";")
        writer.writerow(
            [
                "№", "Дата", "Статус", "Имя", "Телефон", "E-mail", "Организация", "Программа",
                "Слушателей", "Нужен счёт/КП", "Комментарий", "Заметка",
            ]
        )
        for lead in queryset.select_related("program"):
            row = [
                lead.pk,
                timezone.localtime(lead.created_at).strftime("%d.%m.%Y %H:%M"),
                lead.get_status_display(),
                lead.name,
                lead.phone,
                lead.email,
                lead.organization,
                lead.program.title if lead.program else "",
                lead.listeners or "",
                "да" if lead.need_invoice else "нет",
                lead.comment,
                lead.staff_note,
            ]
            writer.writerow([csv_safe(cell) for cell in row])
        return response

    @admin.action(description="Удалить персональные данные (обезличить)")
    def anonymize(self, request, queryset):
        """Стереть ПДн, сохранив саму заявку для статистики (дата, программа, статус)."""
        updated = queryset.update(
            name="Обезличено",
            phone="—",
            email="",
            organization="",
            comment="",
            staff_note="",
            ip=None,
        )
        self.message_user(request, f"Обезличено заявок: {updated}", level=messages.SUCCESS)
