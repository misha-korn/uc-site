"""
Модели раздела «Сведения об образовательной организации» (/sveden/).

Раздел обязателен по Приказу Рособрнадзора № 1493. Каждый подраздел — своя
страница, данные для неё берутся из этих моделей. Поля зафиксированы в
CONTRACT.md (п. 6). У всех моделей есть updated_at — по нему на странице
выводится «Дата обновления сведений».
"""

from django.core.validators import URLValidator
from django.db import models

from core.models import DOCUMENT_FILE_VALIDATORS, DOCUMENT_HELP, IMAGE_FILE_VALIDATORS

# Только http(s)://: в href не должны попасть javascript:, ftp: и т. п.
HTTP_URL_VALIDATOR = URLValidator(schemes=["http", "https"], message="Укажите адрес, начинающийся с http:// или https://")

# Подразделы в порядке п. 6 Требований (+ «Образовательные стандарты» после «Образования»).
# slug совпадает с адресом страницы: /sveden/<slug>/ и с именем URL sveden:<slug>.
SECTIONS = [
    ("common", "Основные сведения"),
    ("struct", "Структура и органы управления образовательной организацией"),
    ("document", "Документы"),
    ("education", "Образование"),
    ("eduStandarts", "Образовательные стандарты и требования"),
    ("managers", "Руководство"),
    ("employees", "Педагогический состав"),
    ("objects", "Материально-техническое обеспечение и оснащенность образовательного процесса. Доступная среда"),
    ("paid_edu", "Платные образовательные услуги"),
    ("budget", "Финансово-хозяйственная деятельность"),
    ("vacant", "Вакантные места для приема (перевода) обучающихся"),
    ("grants", "Стипендии и меры поддержки обучающихся"),
    ("inter", "Международное сотрудничество"),
    ("catering", "Организация питания в образовательной организации"),
]
SECTION_TITLES = dict(SECTIONS)

# Подсказки для поля itemprop документов (методические рекомендации Рособрнадзора).
# Поле допускает и любое другое значение — список только помогает выбрать.
DOCUMENT_ITEMPROP_HINTS = [
    ("ustavDocLink", "Документы → Устав"),
    ("localActStud", "Документы → Правила внутреннего распорядка обучающихся"),
    ("localActOrder", "Документы → Правила внутреннего трудового распорядка"),
    ("localActCollec", "Документы → Коллективный договор"),
    ("priemDocLink", "Документы → Правила приёма обучающихся"),
    ("modeDocLink", "Документы → Режим занятий"),
    ("tekKontrolDocLink", "Документы → Текущий контроль и промежуточная аттестация"),
    ("perevodDocLink", "Документы → Порядок перевода, отчисления и восстановления"),
    ("vozDocLink", "Документы → Возникновение, приостановление, прекращение отношений"),
    ("reportEduDocLink", "Документы → Отчёт о самообследовании"),
    ("prescriptionDocLink", "Документы → Предписания и отчёты об их исполнении"),
    ("divisionClauseDocLink", "Структура → Положение о подразделении"),
    ("licenseDocLink", "Основные сведения → Выписка из реестра лицензий"),
    ("languageEl", "Образование → Языки образования"),
    ("eduChislenEl", "Образование → Численность обучающихся"),
    ("eduPriemEl", "Образование → Результаты приёма"),
    ("eduPerevodEl", "Образование → Результаты перевода, восстановления, отчисления"),
    ("eduFedDoc", "Стандарты → ФГОС (ссылка на НПА)"),
    ("eduStandartDoc", "Стандарты → Собственные образовательные стандарты"),
    ("eduFedTreb", "Стандарты → ФГТ (ссылка на НПА)"),
    ("eduStandartTreb", "Стандарты → Собственные требования"),
    ("paidEdu", "Платные услуги → Порядок оказания платных услуг"),
    ("paidDog", "Платные услуги → Образец договора"),
    ("paidSt", "Платные услуги → Утверждение стоимости обучения"),
    ("finPlanDocLink", "ФХД → План ФХД / бюджетная смета"),
    ("localActObSt", "Стипендии → Локальный акт о мерах поддержки"),
]


class Organization(models.Model):
    """Основные сведения об организации. Запись одна (pk=1) — «одиночка» (singleton)."""

    full_name = models.CharField("полное наименование", max_length=500)
    short_name = models.CharField("сокращённое наименование", max_length=255)
    reg_date = models.DateField("дата создания")
    address = models.CharField("место нахождения (адрес)", max_length=500)
    work_time = models.TextField("режим и график работы", help_text="Каждое правило — с новой строки.")
    phones = models.CharField("телефоны", max_length=255, help_text="Несколько — через «;».")
    emails = models.CharField("электронная почта", max_length=255, help_text="Несколько — через «;».")
    inn = models.CharField("ИНН", max_length=12)
    ogrn = models.CharField("ОГРН", max_length=15)
    license_number = models.CharField("номер лицензии", max_length=100)
    license_date = models.DateField("дата лицензии", null=True, blank=True)
    license_issuer = models.CharField("кем выдана лицензия", max_length=500)
    license_url = models.URLField(
        "ссылка на выписку из реестра лицензий",
        blank=True,
        help_text="Ссылка на запись в реестре лицензий Рособрнадзора / региона.",
    )
    license_file = models.FileField(
        "файл выписки из реестра лицензий",
        upload_to="docs/",
        blank=True,
        validators=DOCUMENT_FILE_VALIDATORS,
        help_text=DOCUMENT_HELP,
    )
    accreditation_note = models.TextField(
        "сведения о государственной аккредитации",
        default=(
            "Государственная аккредитация по программам ДПО и профессионального обучения "
            "не проводится (ст. 92 Федерального закона № 273-ФЗ)"
        ),
    )
    map_embed_url = models.URLField(
        "ссылка для встраивания карты",
        blank=True,
        help_text="Адрес из кода встраивания Яндекс.Карт (атрибут src у iframe).",
    )
    updated_at = models.DateTimeField("изменено", auto_now=True)

    class Meta:
        verbose_name = "основные сведения об организации"
        verbose_name_plural = "основные сведения об организации"

    def __str__(self):
        return self.short_name or self.full_name

    def save(self, *args, **kwargs):
        # Запись всегда одна: какой бы pk ни пришёл, сохраняем как pk=1.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Вернуть единственную запись или None, если её ещё не создали."""
        return cls.objects.filter(pk=1).first()

    @property
    def license_link(self):
        """Ссылка на лицензию: файл, если загружен, иначе внешняя ссылка."""
        if self.license_file:
            return self.license_file.url
        return self.license_url

    @staticmethod
    def _split(value):
        """Разбить строку «a; b; c» на список непустых значений."""
        return [part.strip() for part in (value or "").split(";") if part.strip()]

    @property
    def phone_list(self):
        """Телефоны для шаблонов: [{'text': '+7 (846) ...', 'href': 'tel:+7846...'}]."""
        result = []
        for text in self._split(self.phones):
            digits = "".join(ch for ch in text if ch.isdigit())
            if len(digits) == 11 and digits.startswith("8"):
                digits = "7" + digits[1:]  # 8 (846) ... → +7 (846) ...
            if digits:
                result.append({"text": text, "href": f"tel:+{digits}"})
        return result

    @property
    def email_list(self):
        """Адреса почты для шаблонов: [{'text': 'info@...', 'href': 'mailto:info@...'}]."""
        return [{"text": e, "href": f"mailto:{e}"} for e in self._split(self.emails)]


class Founder(models.Model):
    """Учредитель (itemprop uchredLaw)."""

    name = models.CharField("наименование / ФИО", max_length=500)
    address = models.CharField("адрес", max_length=500, blank=True)
    phone = models.CharField("телефон", max_length=100, blank=True)
    email = models.CharField("e-mail", max_length=255, blank=True)
    website = models.URLField(
        "сайт", max_length=255, blank=True, validators=[HTTP_URL_VALIDATOR], help_text="Напр. https://example.ru"
    )
    order = models.IntegerField("порядок", default=0)
    updated_at = models.DateTimeField("изменено", auto_now=True)

    class Meta:
        verbose_name = "учредитель"
        verbose_name_plural = "учредители"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class EduPlace(models.Model):
    """Место осуществления образовательной деятельности."""

    KIND_CHOICES = [
        ("dop", "Место реализации дополнительных программ"),
        ("oppo", "Место реализации программ профессионального обучения"),
        ("prac", "Место проведения практики"),
        ("podg", "Место практической подготовки"),
        ("set", "Место, не указанное в реестре лицензий (сетевая форма)"),
        ("gia", "Место проведения итоговой аттестации"),
    ]
    ITEMPROPS = {
        "dop": "addressPlaceDop",
        "oppo": "addressPlaceOppo",
        "prac": "addressPlacePrac",
        "podg": "addressPlacePodg",
        "set": "addressPlaceSet",
        "gia": "addressPlaceGia",
    }

    kind = models.CharField("вид места", max_length=5, choices=KIND_CHOICES, default="dop")
    address = models.CharField("адрес", max_length=500)
    order = models.IntegerField("порядок", default=0)
    updated_at = models.DateTimeField("изменено", auto_now=True)

    class Meta:
        verbose_name = "место осуществления образовательной деятельности"
        verbose_name_plural = "места осуществления образовательной деятельности"
        ordering = ["order", "id"]

    def __str__(self):
        return self.address

    @property
    def itemprop(self):
        return self.ITEMPROPS.get(self.kind, "addressPlaceDop")


class Department(models.Model):
    """Структурное подразделение / орган управления (itemprop structOrgUprav)."""

    name = models.CharField("наименование", max_length=300)
    head_fio = models.CharField("ФИО руководителя", max_length=200, blank=True)
    head_post = models.CharField("должность руководителя", max_length=200, blank=True)
    address = models.CharField("место нахождения", max_length=500, blank=True)
    site = models.URLField(
        "сайт", max_length=255, blank=True, validators=[HTTP_URL_VALIDATOR], help_text="Напр. https://example.ru"
    )
    email = models.CharField("e-mail", max_length=255, blank=True)
    clause_file = models.FileField(
        "положение о подразделении (файл)",
        upload_to="docs/",
        blank=True,
        validators=DOCUMENT_FILE_VALIDATORS,
        help_text=DOCUMENT_HELP,
    )
    order = models.IntegerField("порядок", default=0)
    updated_at = models.DateTimeField("изменено", auto_now=True)

    class Meta:
        verbose_name = "подразделение / орган управления"
        verbose_name_plural = "структура и органы управления"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class Document(models.Model):
    """Документ, выводимый в одном из подразделов «Сведений»."""

    section = models.CharField("подраздел", max_length=20, choices=SECTIONS, default="document")
    itemprop = models.CharField(
        "микроразметка (itemprop)",
        max_length=60,
        blank=True,
        help_text=(
            "Служебная метка для проверки сайта Рособрнадзором. Выберите из подсказок при вводе: "
            "Устав — ustavDocLink; Правила распорядка обучающихся — localActStud; "
            "Правила трудового распорядка — localActOrder; Коллективный договор — localActCollec; "
            "Правила приёма — priemDocLink; Режим занятий — modeDocLink; "
            "Текущий контроль — tekKontrolDocLink; Перевод/отчисление — perevodDocLink; "
            "Возникновение отношений — vozDocLink; Самообследование — reportEduDocLink; "
            "Предписания — prescriptionDocLink. Если не уверены — оставьте пустым."
        ),
    )
    title = models.CharField(
        "название документа",
        max_length=500,
        help_text="Пишется в ссылке, поэтому должно понятно описывать документ (п. 4 Требований).",
    )
    file = models.FileField(
        "файл", upload_to="docs/", blank=True, validators=DOCUMENT_FILE_VALIDATORS, help_text=DOCUMENT_HELP
    )
    url = models.URLField("или внешняя ссылка", blank=True)
    number = models.CharField("номер", max_length=100, blank=True)
    doc_date = models.DateField("дата документа", null=True, blank=True)
    signed = models.BooleanField("подписан электронной подписью", default=False)
    signer = models.CharField(
        "кто подписал",
        max_length=255,
        blank=True,
        help_text="Напр. «Иванов И.И., директор».",
    )
    signed_at = models.DateTimeField("дата и время подписи", null=True, blank=True)
    order = models.IntegerField("порядок", default=0)
    is_published = models.BooleanField("опубликован", default=True)
    updated_at = models.DateTimeField("изменено", auto_now=True)

    class Meta:
        verbose_name = "документ"
        verbose_name_plural = "документы"
        ordering = ["section", "order", "id"]

    def __str__(self):
        return self.title

    @property
    def link(self):
        """Адрес для ссылки: загруженный файл или внешняя ссылка ('' если нет ничего)."""
        if self.file:
            return self.file.url
        return self.url or ""


class Manager(models.Model):
    """Руководитель или заместитель."""

    ROLE_CHOICES = [
        ("head", "Руководитель"),
        ("zam", "Заместитель руководителя"),
    ]
    ITEMPROPS = {"head": "rucovodstvo", "zam": "rucovodstvoZam"}

    role = models.CharField("роль", max_length=5, choices=ROLE_CHOICES, default="zam")
    fio = models.CharField("ФИО", max_length=200)
    post = models.CharField("должность", max_length=200)
    phone = models.CharField("телефон", max_length=100, blank=True)
    email = models.CharField("e-mail", max_length=255, blank=True)
    # Pillow не используем, поэтому обычный FileField, а не ImageField.
    photo = models.FileField(
        "фото",
        upload_to="managers/",
        blank=True,
        validators=IMAGE_FILE_VALIDATORS,
        help_text="JPG, PNG или WEBP, до 20 МБ.",
    )
    order = models.IntegerField("порядок", default=0)
    updated_at = models.DateTimeField("изменено", auto_now=True)

    class Meta:
        verbose_name = "руководитель"
        verbose_name_plural = "руководство"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.fio} — {self.post}"

    @property
    def itemprop(self):
        return self.ITEMPROPS.get(self.role, "rucovodstvoZam")


class Teacher(models.Model):
    """Педагогический работник (itemprop teachingStaff)."""

    fio = models.CharField("ФИО", max_length=200)
    post = models.CharField("должность", max_length=200)
    disciplines = models.TextField("преподаваемые дисциплины")
    level = models.TextField("уровень образования, специальность, квалификация")
    degree = models.CharField("учёная степень", max_length=200, default="Нет")
    academic_title = models.CharField("учёное звание", max_length=200, default="Нет")
    qualification = models.TextField("повышение квалификации (за 3 года)")
    retraining = models.TextField("профессиональная переподготовка", blank=True)
    experience = models.PositiveSmallIntegerField("стаж в профессиональной сфере, лет", default=0)
    programs = models.ManyToManyField(
        "core.Program",
        verbose_name="программы, в которых участвует",
        blank=True,
        related_name="teachers",
    )
    order = models.IntegerField("порядок", default=0)
    updated_at = models.DateTimeField("изменено", auto_now=True)

    class Meta:
        verbose_name = "преподаватель"
        verbose_name_plural = "педагогический состав"
        ordering = ["order", "fio"]

    def __str__(self):
        return self.fio


class Facility(models.Model):
    """Объект материально-технического обеспечения."""

    KIND_CHOICES = [
        ("cab", "Учебный кабинет"),
        ("prac", "Объект для практических занятий"),
        ("libr", "Библиотека"),
        ("sport", "Объект спорта"),
    ]

    kind = models.CharField("вид объекта", max_length=5, choices=KIND_CHOICES, default="cab")
    name = models.CharField("наименование", max_length=300)
    address = models.CharField("адрес", max_length=500)
    equipment = models.TextField("оснащённость")
    ovz = models.TextField(
        "приспособленность для инвалидов и лиц с ОВЗ",
        default="Приспособлен для использования инвалидами и лицами с ОВЗ",
    )
    order = models.IntegerField("порядок", default=0)
    updated_at = models.DateTimeField("изменено", auto_now=True)

    class Meta:
        verbose_name = "объект МТО"
        verbose_name_plural = "материально-техническое обеспечение"
        ordering = ["kind", "order", "id"]

    def __str__(self):
        return self.name


class VacantPlace(models.Model):
    """Вакантные места по программе (одна запись на программу).

    На странице /sveden/vacant/ выводятся ВСЕ опубликованные программы: если записи для программы
    нет, строка показывается с нулями (см. sveden.views.vacant).
    """

    program = models.OneToOneField(
        "core.Program",
        verbose_name="программа",
        on_delete=models.CASCADE,
        related_name="vacant_place",
    )
    fed = models.PositiveIntegerField("за счёт федерального бюджета", default=0)
    sub = models.PositiveIntegerField("за счёт бюджета субъекта РФ", default=0)
    mest = models.PositiveIntegerField("за счёт местного бюджета", default=0)
    paid = models.PositiveIntegerField("по договорам об оказании платных услуг", default=0)
    updated_at = models.DateTimeField("изменено", auto_now=True)

    class Meta:
        verbose_name = "вакантные места"
        verbose_name_plural = "вакантные места"
        ordering = ["program__order", "program__title"]

    def __str__(self):
        return f"Вакантные места: {self.program}"


class SvedenField(models.Model):
    """Произвольное текстовое сведение на странице подраздела (подпись + значение)."""

    page = models.CharField("подраздел", max_length=20, choices=SECTIONS)
    itemprop = models.CharField(
        "микроразметка (itemprop)",
        max_length=60,
        blank=True,
        help_text="Служебная метка для проверки сайта Рособрнадзором. Если не уверены — не меняйте.",
    )
    label = models.CharField("подпись", max_length=500)
    value = models.TextField("значение", help_text="Переносы строк сохраняются.")
    order = models.IntegerField("порядок", default=0)
    updated_at = models.DateTimeField("изменено", auto_now=True)

    class Meta:
        verbose_name = "текстовое сведение"
        verbose_name_plural = "текстовые сведения"
        ordering = ["page", "order", "id"]

    def __str__(self):
        return self.label
