"""
Форма заявки на обучение (CONTRACT.md, п. 8).

Имена полей неизменны: name, phone, email, organization, program, comment,
listeners, need_invoice, consent, website (listeners и need_invoice добавлены по итогам
бизнес-ревью: сколько слушателей и нужен ли счёт/КП для организации). Поле website — «ловушка для ботов» (honeypot): человек его
не видит (скрыто CSS-классом hp), а бот заполняет все поля подряд.
"""

import re

from django import forms
from django.urls import reverse
from django.utils.html import format_html

from .models import Lead, Program

# Телефон: «+» только в начале, дальше цифры, пробелы, скобки и дефисы. Не длиннее 20 символов.
PHONE_ALLOWED_RE = re.compile(r"^\+?[\d\s()\-]+$")
PHONE_MAX_LENGTH = 20


def normalize_phone(raw):
    """Привести телефон к единому виду для хранения и звонка по ссылке tel:.

    Российские номера → «+7XXXXXXXXXX»: «8 (900) 123-45-67», «+7 900 …», «900 123-45-67» (10 цифр).
    Остальные (иностранные) → «+» и цифры: «+375 29 123 45 67» → «+375291234567».
    Проверку формата делает LeadForm.clean_phone — сюда приходит уже допустимая строка.
    """
    digits = re.sub(r"\D", "", raw)
    has_plus = raw.strip().startswith("+")
    if len(digits) == 11 and (digits[0] == "7" or (digits[0] == "8" and not has_plus)):
        return "+7" + digits[1:]
    if len(digits) == 10 and not has_plus:
        return "+7" + digits
    return "+" + digits


def consent_label():
    """Текст чекбокса — ТОЛЬКО согласие на обработку ПДн, со ссылкой на текст согласия.

    Согласие должно быть отдельным от политики (ч. 1 ст. 9 152-ФЗ в ред. 156-ФЗ), поэтому слов
    про «ознакомлен с политикой» в чекбоксе нет: ссылку на политику шаблон выводит рядом отдельной строкой.
    """
    return format_html(
        'Я даю <a href="{}" target="_blank" rel="noopener">согласие на обработку персональных данных</a>',
        reverse("core:consent"),
    )


# Тексты ошибок — из docs/SEO.md, §5 «Ошибки формы».
MSG_NAME_REQUIRED = "Как к вам обращаться? Укажите имя."
MSG_NAME_TOO_LONG = "Имя слишком длинное — сократите до 120 символов."
MSG_PHONE_REQUIRED = "Укажите телефон — по нему мы свяжемся с вами."
MSG_PHONE_INVALID = "Проверьте номер: нужно 10–15 цифр, например +7 900 123-45-67."
MSG_LISTENERS_INVALID = "Укажите число слушателей от 1 до 500."
MSG_EMAIL_INVALID = "Проверьте e-mail: похоже, в адресе опечатка."
MSG_COMMENT_TOO_LONG = "Комментарий слишком длинный — до 2000 символов."
MSG_CONSENT_REQUIRED = "Без согласия на обработку данных мы не сможем принять заявку."
MSG_RATE_LIMIT = "Слишком много заявок с одного адреса. Попробуйте через 10 минут или позвоните нам{phones}."
MSG_FORM_SUMMARY = "Проверьте поля, отмеченные красным."


class LeadForm(forms.Form):
    """Заявка с сайта. Валидация полностью серверная — браузерным проверкам не доверяем."""

    summary_error = MSG_FORM_SUMMARY  # общая фраза над формой (шаблон может вывести при form.errors)

    name = forms.CharField(
        label="Ваше имя",
        max_length=120,
        error_messages={"required": MSG_NAME_REQUIRED, "max_length": MSG_NAME_TOO_LONG},
        widget=forms.TextInput(attrs={"autocomplete": "name", "placeholder": "Иван"}),
    )
    phone = forms.CharField(
        label="Телефон",
        max_length=PHONE_MAX_LENGTH,
        error_messages={"required": MSG_PHONE_REQUIRED, "max_length": MSG_PHONE_INVALID},
        widget=forms.TextInput(
            attrs={"type": "tel", "autocomplete": "tel", "inputmode": "tel", "placeholder": "+7 (___) ___-__-__"}
        ),
    )
    email = forms.EmailField(
        label="E-mail (необязательно)",
        required=False,
        max_length=254,
        error_messages={"invalid": MSG_EMAIL_INVALID, "max_length": MSG_EMAIL_INVALID},
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "name@company.ru"}),
    )
    organization = forms.CharField(
        label="Организация (если обучение оплачивает компания)",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"autocomplete": "organization"}),
    )
    program = forms.ModelChoiceField(
        label="Программа (необязательно)",
        required=False,
        queryset=Program.objects.filter(is_published=True).order_by("order", "title"),
        empty_label="Не знаю — помогите подобрать",
    )
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        max_length=2000,
        error_messages={"max_length": MSG_COMMENT_TOO_LONG},
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Удобные даты, нужен ли выезд преподавателя"}),
    )
    listeners = forms.IntegerField(
        label="Количество слушателей",
        required=False,
        min_value=1,
        max_value=500,
        error_messages={
            "invalid": MSG_LISTENERS_INVALID,
            "min_value": MSG_LISTENERS_INVALID,
            "max_value": MSG_LISTENERS_INVALID,
        },
        widget=forms.NumberInput(attrs={"inputmode": "numeric", "placeholder": "1"}),
    )
    need_invoice = forms.BooleanField(
        label="Нужен счёт / КП для организации",
        required=False,
    )
    consent = forms.BooleanField(
        label="Я даю согласие на обработку персональных данных",
        required=True,
        error_messages={"required": MSG_CONSENT_REQUIRED},
    )
    # Honeypot: должно остаться пустым. Скрывается в шаблоне классом hp.
    website = forms.CharField(
        label="Сайт (не заполняйте это поле)",
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ссылки в подписи строим здесь, а не при импорте модуля (URL-ы к этому моменту уже загружены).
        self.fields["consent"].label = consent_label()

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if not name:
            raise forms.ValidationError(MSG_NAME_REQUIRED)
        if re.search(r"https?://|www\.|<|>", name, re.IGNORECASE):
            raise forms.ValidationError("Имя не должно содержать ссылок и спецсимволов.")
        return name

    def clean_phone(self):
        """Телефон: цифры, пробелы, скобки, дефисы и «+» в начале; до 20 символов; цифр — 10–15.

        Возвращает нормализованный номер (+7XXXXXXXXXX для России) — см. normalize_phone().
        """
        raw = self.cleaned_data["phone"].strip()
        digits = re.sub(r"\D", "", raw)
        if len(raw) > PHONE_MAX_LENGTH or not PHONE_ALLOWED_RE.match(raw) or not 10 <= len(digits) <= 15:
            raise forms.ValidationError(MSG_PHONE_INVALID)
        return normalize_phone(raw)

    def clean_organization(self):
        return " ".join(self.cleaned_data.get("organization", "").split())

    def clean_comment(self):
        comment = self.cleaned_data.get("comment", "").strip()
        if len(re.findall(r"https?://", comment, re.IGNORECASE)) > 2:
            raise forms.ValidationError("Слишком много ссылок в комментарии.")
        return comment

    @property
    def is_bot(self):
        """True, если заполнено скрытое поле-ловушка (проверять после is_valid())."""
        return bool((self.cleaned_data or {}).get("website") or self.data.get("website"))

    def to_lead(self, *, ip=None, consent_version="", consent_at=None):
        """Создать (не сохраняя) объект Lead из проверенных данных формы."""
        data = self.cleaned_data
        return Lead(
            name=data["name"],
            phone=data["phone"],
            email=data.get("email", ""),
            organization=data.get("organization", ""),
            program=data.get("program"),
            comment=data.get("comment", ""),
            listeners=data.get("listeners"),
            need_invoice=bool(data.get("need_invoice")),
            consent=True,
            consent_version=consent_version,
            consent_at=consent_at,
            ip=ip,
        )
