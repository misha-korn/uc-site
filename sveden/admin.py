"""
Панель заказчика: раздел «Сведения об образовательной организации».

Подсказки (help_text) у полей написаны для заказчика: что вписывать и куда это
попадёт на сайте. Поле itemprop у документов — с выпадающими подсказками
(список рекомендаций Рособрнадзора), но можно вписать и своё значение.
"""

from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    DOCUMENT_ITEMPROP_HINTS,
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


class ItempropHintWidget(forms.TextInput):
    """Текстовое поле с подсказками (HTML datalist): можно выбрать из списка или ввести своё."""

    def __init__(self, hints, attrs=None):
        self.hints = hints
        super().__init__(attrs={"list": "itemprop-hints", "size": 30, **(attrs or {})})

    def render(self, name, value, attrs=None, renderer=None):
        html = super().render(name, value, attrs, renderer)
        options = format_html(
            "".join('<option value="{}">{}</option>' for _ in self.hints),
            *[part for pair in self.hints for part in pair],
        )
        return format_html('{}<datalist id="itemprop-hints">{}</datalist>', html, options)


# --- Основные сведения: одна запись -----------------------------------------

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """«Одиночка»: создать можно только одну запись, удалить нельзя."""

    fieldsets = (
        ("Наименование", {"fields": ("full_name", "short_name", "reg_date")}),
        ("Контакты", {"fields": ("address", "work_time", "phones", "emails", "map_embed_url")}),
        ("Реквизиты", {"fields": ("inn", "ogrn")}),
        (
            "Лицензия и аккредитация",
            {
                "fields": (
                    "license_number",
                    "license_date",
                    "license_issuer",
                    "license_url",
                    "license_file",
                    "accreditation_note",
                ),
                "description": "Выписку из реестра лицензий можно загрузить файлом или дать ссылку на реестр.",
            },
        ),
    )
    list_display = ("short_name", "phones", "updated_at")

    def has_add_permission(self, request):
        return not Organization.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        """Сразу открываем форму единственной записи вместо пустого списка."""
        from django.shortcuts import redirect

        org = Organization.load()
        if org is not None:
            return redirect(reverse("admin:sveden_organization_change", args=[org.pk]))
        return redirect(reverse("admin:sveden_organization_add"))


@admin.register(Founder)
class FounderAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "order")
    list_editable = ("order",)


@admin.register(EduPlace)
class EduPlaceAdmin(admin.ModelAdmin):
    list_display = ("address", "kind", "order")
    list_editable = ("order",)
    list_filter = ("kind",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "head_fio", "head_post", "order")
    list_editable = ("order",)
    search_fields = ("name", "head_fio")


class DocumentAdminForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = "__all__"
        widgets = {"itemprop": ItempropHintWidget(DOCUMENT_ITEMPROP_HINTS)}

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("signed") and not cleaned.get("signer"):
            self.add_error("signer", "Укажите, кто подписал документ (напр. «Иванов И.И., директор»).")
        return cleaned


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    form = DocumentAdminForm
    list_display = ("title", "section", "itemprop", "signed", "doc_date", "is_published", "order", "file_link")
    list_editable = ("is_published", "order")
    list_filter = ("section", "signed", "is_published")
    search_fields = ("title", "number", "itemprop")
    save_on_top = True
    fieldsets = (
        (None, {"fields": ("section", "title", "itemprop", "is_published", "order")}),
        (
            "Файл или ссылка",
            {"fields": ("file", "url"), "description": "Загрузите PDF с текстовым слоем или укажите внешнюю ссылку."},
        ),
        ("Реквизиты", {"fields": ("number", "doc_date")}),
        ("Электронная подпись", {"fields": ("signed", "signer", "signed_at")}),
    )

    @admin.display(description="файл")
    def file_link(self, obj):
        if obj.link:
            return format_html('<a href="{}" target="_blank">открыть</a>', obj.link)
        return "—"


@admin.register(Manager)
class ManagerAdmin(admin.ModelAdmin):
    list_display = ("fio", "post", "role", "phone", "email", "order")
    list_editable = ("order",)
    list_filter = ("role",)


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("fio", "post", "experience", "order")
    list_editable = ("order",)
    search_fields = ("fio", "disciplines")
    list_filter = ("programs__category",)
    filter_horizontal = ("programs",)


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "address", "order")
    list_editable = ("order",)
    list_filter = ("kind",)
    search_fields = ("name", "address")


@admin.register(VacantPlace)
class VacantPlaceAdmin(admin.ModelAdmin):
    """Числа вакантных мест. Программы без записи выводятся на сайте с нулями."""

    list_display = ("program", "fed", "sub", "mest", "paid")
    list_editable = ("fed", "sub", "mest", "paid")
    list_select_related = ("program",)
    autocomplete_fields = ("program",)


@admin.register(SvedenField)
class SvedenFieldAdmin(admin.ModelAdmin):
    list_display = ("label", "page", "itemprop", "order")
    list_editable = ("order",)
    list_filter = ("page",)
    search_fields = ("label", "value", "itemprop")
