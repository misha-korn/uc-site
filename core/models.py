"""
Модели «витрины» учебного центра: направления, программы обучения и заявки.

Имена полей зафиксированы в CONTRACT.md (п. 6) — на них опираются шаблоны,
админка, демо-данные и экспорт. Переименовывать поля нельзя.
"""

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.deconstruct import deconstructible

# --- Проверка загружаемых файлов ------------------------------------------------
# Разрешаем только «документные» форматы: HTML/SVG/JS, загруженные в media, браузер выполнил бы
# как страницу нашего сайта (XSS). Лимит размера — 20 МБ (крупнее nginx всё равно не пропустит).
DOCUMENT_EXTENSIONS = ["pdf", "sig", "p7s", "doc", "docx", "xls", "xlsx", "odt", "ods"]
IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
MAX_UPLOAD_MB = 20


@deconstructible
class MaxFileSizeValidator:
    """Ошибка, если файл больше limit_mb мегабайт."""

    def __init__(self, limit_mb=MAX_UPLOAD_MB):
        self.limit_mb = limit_mb

    def __call__(self, value):
        size = getattr(value, "size", None)
        if size is not None and size > self.limit_mb * 1024 * 1024:
            raise ValidationError(
                "Файл слишком большой: %(size).1f МБ. Максимум — %(limit)s МБ.",
                code="file_too_large",
                params={"size": size / 1024 / 1024, "limit": self.limit_mb},
            )

    def __eq__(self, other):
        return isinstance(other, MaxFileSizeValidator) and other.limit_mb == self.limit_mb


DOCUMENT_FILE_VALIDATORS = [
    FileExtensionValidator(
        DOCUMENT_EXTENSIONS,
        message="Недопустимый формат «%(extension)s». Можно загрузить: %(allowed_extensions)s.",
    ),
    MaxFileSizeValidator(MAX_UPLOAD_MB),
]
IMAGE_FILE_VALIDATORS = [
    FileExtensionValidator(
        IMAGE_EXTENSIONS,
        message="Недопустимый формат «%(extension)s». Для фото можно: %(allowed_extensions)s.",
    ),
    MaxFileSizeValidator(MAX_UPLOAD_MB),
]
DOCUMENT_HELP = "PDF с текстовым слоем (также DOC/DOCX, XLS/XLSX, ODT/ODS, файл подписи SIG/P7S), до 20 МБ."


class ProgramCategory(models.Model):
    """Направление обучения (охрана труда, пожарная безопасность и т.д.)."""

    ICON_CHOICES = [
        ("shield", "Щит (охрана труда)"),
        ("fire", "Огонь (пожарная безопасность)"),
        ("helmet", "Каска (промышленная безопасность)"),
        ("cross", "Крест (первая помощь)"),
        ("bolt", "Молния (электробезопасность)"),
        ("crane", "Кран (стропальщики, люльки)"),
        ("weld", "Сварка (сварщики)"),
        ("factory", "Завод (рабочие профессии)"),
    ]

    name = models.CharField("название", max_length=200)
    slug = models.SlugField(
        "адрес (slug)",
        max_length=100,
        unique=True,
        help_text="Латиницей, без пробелов: используется в адресе страницы, напр. ohrana-truda.",
    )
    short = models.TextField("краткое описание", blank=True)
    icon = models.CharField("иконка", max_length=20, choices=ICON_CHOICES, default="shield")
    order = models.IntegerField("порядок", default=0, help_text="Чем меньше число, тем выше в списке.")

    class Meta:
        verbose_name = "направление обучения"
        verbose_name_plural = "направления обучения"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"{reverse('core:program_list')}?cat={self.slug}"


class Program(models.Model):
    """Образовательная программа (курс)."""

    KIND_OT = "ot"
    KIND_PK = "pk"
    KIND_PP = "pp"
    KIND_PO = "po"
    KIND_CHOICES = [
        (KIND_OT, "Обучение по охране труда"),
        (KIND_PK, "Повышение квалификации"),
        (KIND_PP, "Профессиональная переподготовка"),
        (KIND_PO, "Профессиональное обучение"),
    ]

    category = models.ForeignKey(
        ProgramCategory,
        verbose_name="направление",
        on_delete=models.PROTECT,
        related_name="programs",
    )
    title = models.CharField("название программы", max_length=300)
    slug = models.SlugField("адрес (slug)", max_length=150, unique=True)
    kind = models.CharField("вид программы", max_length=2, choices=KIND_CHOICES, default=KIND_PK)
    code = models.CharField(
        "код профессии",
        max_length=20,
        blank=True,
        help_text="Код профессии по ОКПДТР — только для профессионального обучения, напр. 18897.",
    )
    hours = models.PositiveIntegerField("объём, часов")
    duration = models.CharField("срок обучения", max_length=100, help_text="Напр. «5 дней» или «2 месяца».")
    form = models.CharField(
        "форма обучения",
        max_length=200,
        default="Очная",
        help_text="Напр. «Очная, очно-заочная, с применением ДОТ».",
    )
    price = models.PositiveIntegerField("стоимость, руб.")
    document_issued = models.CharField(
        "выдаваемый документ",
        max_length=300,
        help_text="Напр. «Удостоверение о повышении квалификации».",
    )
    short = models.TextField("краткое описание", help_text="1–2 предложения для карточки программы.")
    description = models.TextField("подробное описание")
    audience = models.TextField("для кого программа", blank=True)
    disciplines = models.TextField(
        "учебные модули (дисциплины)",
        help_text="Каждый модуль — с новой строки.",
    )
    practice = models.TextField("практика", blank=True)
    language = models.CharField("язык обучения", max_length=50, default="Русский")
    is_popular = models.BooleanField("популярная (показывать на главной)", default=False)
    is_published = models.BooleanField(
        "опубликована",
        default=True,
        help_text="Снимите галочку, чтобы скрыть программу с сайта, не удаляя её.",
    )
    order = models.IntegerField("порядок", default=0)
    op_file = models.FileField(
        "образовательная программа (файл)", upload_to="programs/", blank=True, validators=DOCUMENT_FILE_VALIDATORS, help_text=DOCUMENT_HELP
    )
    plan_file = models.FileField(
        "учебный план", upload_to="programs/", blank=True, validators=DOCUMENT_FILE_VALIDATORS, help_text=DOCUMENT_HELP
    )
    schedule_file = models.FileField(
        "календарный учебный график", upload_to="programs/", blank=True, validators=DOCUMENT_FILE_VALIDATORS, help_text=DOCUMENT_HELP
    )
    rpd_file = models.FileField(
        "рабочие программы модулей", upload_to="programs/", blank=True, validators=DOCUMENT_FILE_VALIDATORS, help_text=DOCUMENT_HELP
    )
    methodology_file = models.FileField(
        "методические материалы", upload_to="programs/", blank=True, validators=DOCUMENT_FILE_VALIDATORS, help_text=DOCUMENT_HELP
    )
    updated_at = models.DateTimeField("изменено", auto_now=True)

    class Meta:
        verbose_name = "программа обучения"
        verbose_name_plural = "программы обучения"
        ordering = ["order", "title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("core:program_detail", kwargs={"slug": self.slug})

    @property
    def level_display(self):
        """Уровень образования для раздела «Сведения» (п. 10 Требований)."""
        if self.kind == self.KIND_PO:
            return "Профессиональное обучение"
        return "Дополнительное профессиональное образование"

    @property
    def disciplines_list(self):
        """Список модулей: по одной непустой строке поля disciplines."""
        return [line.strip() for line in (self.disciplines or "").splitlines() if line.strip()]


class Lead(models.Model):
    """Заявка с сайта. Содержит персональные данные — обращаться бережно (152-ФЗ)."""

    STATUS_NEW = "new"
    STATUS_CHOICES = [
        ("new", "Новая"),
        ("work", "В работе"),
        ("done", "Обработана"),
        ("spam", "Спам"),
    ]

    name = models.CharField("имя", max_length=120)
    phone = models.CharField("телефон", max_length=30)
    email = models.EmailField("e-mail", blank=True)
    organization = models.CharField("организация", max_length=255, blank=True)
    program = models.ForeignKey(
        Program,
        verbose_name="программа",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )
    comment = models.TextField("комментарий", max_length=2000, blank=True)
    listeners = models.PositiveSmallIntegerField(
        "количество слушателей",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(500)],
    )
    need_invoice = models.BooleanField("нужен счёт / КП для организации", default=False)
    consent = models.BooleanField("согласие на обработку ПДн", default=False)
    consent_version = models.CharField("версия текста согласия", max_length=100, blank=True)
    consent_at = models.DateTimeField("дата и время согласия", null=True, blank=True)
    ip = models.GenericIPAddressField("IP-адрес", null=True, blank=True)
    created_at = models.DateTimeField("создана", auto_now_add=True)
    status = models.CharField("статус", max_length=10, choices=STATUS_CHOICES, default=STATUS_NEW)
    staff_note = models.TextField("заметка менеджера", blank=True)

    class Meta:
        verbose_name = "заявка"
        verbose_name_plural = "заявки"
        ordering = ["-created_at"]

    def __str__(self):
        # Без имени: строка попадает в журнал действий админки (LogEntry.object_repr) и в сообщения —
        # персональные данные там не нужны (152-ФЗ).
        return f"Заявка #{self.pk}"
