"""
Загрузка демо-данных: python manage.py seed_demo [--reset] [--file путь.json] [--no-pdf]

Что делает:
1. Читает seed/demo_content.json (формат — CONTRACT.md, п. 11).
2. Создаёт/обновляет все записи (update_or_create) — команду можно запускать
   сколько угодно раз, дублей не будет.
3. Для документов без файла и ссылки и для файлов программ генерирует демо-PDF
   (sveden/demo_pdf.py) и кладёт их в MEDIA_ROOT.
4. Если задана переменная окружения DEMO_ADMIN_PASSWORD — создаёт (или обновляет)
   суперпользователя admin с этим паролем.

5. Для подразделений без файла положения генерирует демо-PDF «Положение о <подразделении>»
   (поле Department.clause_file — ссылка divisionClauseDocLink в таблице «Структура»).

--reset — сначала удалить все данные сайта (кроме заявок и пользователей) и
          сгенерированные демо-PDF, затем загрузить заново. Вне демо-стенда (SITE_DEMO=0)
          дополнительно нужен флаг --force — защита от случайной очистки боевого сайта.
--force — подтвердить --reset на сайте с SITE_DEMO=0.

Пароль DEMO_ADMIN_PASSWORD проверяется валидаторами Django (длина, «популярные» пароли, только цифры).
Слабый пароль на боевом сайте (SITE_DEMO=0) не принимается — admin не создаётся; на демо-стенде —
только предупреждение.
"""

import json
import os
from datetime import datetime, time
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction
from django.utils import timezone

from core.models import Program, ProgramCategory
from sveden.demo_pdf import generate_demo_pdf
from sveden.models import (
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

DEMO_PREFIX = "demo-"  # имена сгенерированных файлов начинаются с этого префикса

PROGRAM_FILES = [
    ("op_file", "Образовательная программа"),
    ("plan_file", "Учебный план"),
    ("schedule_file", "Календарный учебный график"),
    ("rpd_file", "Рабочие программы учебных модулей"),
    ("methodology_file", "Методические и иные материалы"),
]


def model_values(model, data, skip=()):
    """Оставить из словаря только поля модели и привести строки к нужным типам (даты и т.д.).

    Файловые, M2M, FK и служебные поля пропускаются — их обрабатываем отдельно.
    """
    result = {}
    for field in model._meta.get_fields():
        if not getattr(field, "concrete", False) or field.name in skip:
            continue
        if field.primary_key or field.is_relation or isinstance(field, models.FileField):
            continue
        if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
            continue
        if field.name not in data:
            continue
        value = data[field.name]
        if value is None and not field.null:
            continue  # null в JSON для обязательного поля — оставляем значение по умолчанию
        if value is not None:
            value = field.to_python(value)
        result[field.name] = value
    return result


class Command(BaseCommand):
    help = "Загрузить демо-данные учебного центра из seed/demo_content.json (идемпотентно)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Удалить данные сайта перед загрузкой.")
        parser.add_argument(
            "--file",
            default=str(settings.BASE_DIR / "seed" / "demo_content.json"),
            help="Путь к JSON с демо-данными (по умолчанию seed/demo_content.json).",
        )
        parser.add_argument("--no-pdf", action="store_true", help="Не генерировать демо-PDF.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Разрешить --reset при SITE_DEMO=0 (боевой сайт: данные будут удалены!).",
        )

    # --- точка входа --------------------------------------------------------
    def handle(self, *args, **options):
        if options["reset"] and not settings.SITE_DEMO and not options["force"]:
            raise CommandError(
                "--reset удаляет ВСЕ сведения сайта (программы, документы, педагогов). "
                "Сайт работает не в демо-режиме (SITE_DEMO=0) — если вы уверены, добавьте флаг --force."
            )
        path = Path(options["file"])
        if not path.is_file():
            raise CommandError(f"Файл с демо-данными не найден: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Ошибка в JSON {path}: {exc}") from exc

        self.make_pdf = not options["no_pdf"]
        self.pdf_count = 0
        self.written_files = set()  # абсолютные пути PDF, созданных этим запуском

        with transaction.atomic():
            if options["reset"]:
                self.reset()
            self.org = self.load_organization(data.get("organization"))
            self.load_simple(Founder, data.get("founders", []), lookup=("name",))
            self.load_simple(EduPlace, data.get("edu_places", []), lookup=("kind", "address"))
            categories = self.load_simple(ProgramCategory, data.get("categories", []), lookup=("slug",))
            self.load_programs(data.get("programs", []), {c.slug: c for c in categories})
            departments = self.load_simple(Department, data.get("departments", []), lookup=("name",))
            self.load_simple(Manager, data.get("managers", []), lookup=("role", "fio"))
            self.default_signer = self.get_default_signer()
            self.load_documents(data.get("documents", []))
            self.load_teachers(data.get("teachers", []))
            self.load_simple(Facility, data.get("facilities", []), lookup=("kind", "name"))
            self.load_vacant(data.get("vacant", []))
            self.load_simple(SvedenField, data.get("fields", []), lookup=("page", "label"))
            if self.make_pdf:
                self.generate_program_files()
                self.generate_department_clauses(departments)

        self.create_admin()
        self.stdout.write(
            self.style.SUCCESS(
                f"Демо-данные загружены: программ {Program.objects.count()}, "
                f"документов {Document.objects.count()}, создано PDF {self.pdf_count}."
            )
        )

    # --- очистка ------------------------------------------------------------
    def reset(self):
        for model in (VacantPlace, Teacher, Document, SvedenField, Facility, Manager, Department, EduPlace, Founder):
            model.objects.all().delete()
        # Программы с заявками не удаляем каскадом: у Lead.program стоит SET_NULL.
        Program.objects.all().delete()
        ProgramCategory.objects.all().delete()
        Organization.objects.all().delete()
        files = []
        for sub in ("docs", "programs"):
            folder = Path(settings.MEDIA_ROOT) / sub
            if folder.is_dir():
                files += list(folder.glob(f"{DEMO_PREFIX}*.pdf"))

        def remove_files():
            # Файлы удаляем только после успешного COMMIT: если загрузка упадёт и транзакция
            # откатится, записи в базе останутся — и ссылки на их PDF тоже должны остаться рабочими.
            # Файлы, заново созданные этой же загрузкой (то же имя), не трогаем.
            for file in files:
                if file.resolve() not in self.written_files:
                    file.unlink(missing_ok=True)

        transaction.on_commit(remove_files)
        self.stdout.write(f"Очистка: данные удалены, демо-PDF к удалению: {len(files)}")

    # --- загрузчики -----------------------------------------------------------
    def load_organization(self, data):
        if not data:
            return Organization.load()
        values = model_values(Organization, data)
        org, _ = Organization.objects.update_or_create(pk=1, defaults=values)
        return org

    def load_simple(self, model, rows, lookup):
        """Общий загрузчик: update_or_create по полям lookup, остальные — в defaults."""
        objects = []
        has_order = any(f.name == "order" for f in model._meta.fields)
        for index, row in enumerate(rows, start=1):
            values = model_values(model, row)
            if has_order:
                values.setdefault("order", index)  # order из JSON важнее; нет — по порядку в файле
            missing = [key for key in lookup if key not in values]
            if missing:
                raise CommandError(f"{model.__name__}: в записи №{index} нет полей {missing}")
            keys = {key: values.pop(key) for key in lookup}
            obj, _ = model.objects.update_or_create(**keys, defaults=values)
            objects.append(obj)
        self.stdout.write(f"  {model._meta.verbose_name_plural}: {len(objects)}")
        return objects

    def load_programs(self, rows, categories):
        count = 0
        for index, row in enumerate(rows, start=1):
            cat_slug = row.get("category")
            if cat_slug not in categories:
                existing = ProgramCategory.objects.filter(slug=cat_slug).first()
                if existing is None:
                    raise CommandError(f"Программа {row.get('slug')}: неизвестное направление «{cat_slug}»")
                categories[cat_slug] = existing
            values = model_values(Program, row)
            values.setdefault("order", index)
            values["category"] = categories[cat_slug]
            slug = values.pop("slug")
            Program.objects.update_or_create(slug=slug, defaults=values)
            count += 1
        self.stdout.write(f"  программы обучения: {count}")

    def load_documents(self, rows):
        for index, row in enumerate(rows, start=1):
            values = model_values(Document, row)
            values.setdefault("order", index)
            values.setdefault("is_published", True)
            if values.get("signed"):
                values.setdefault("signer", self.default_signer)
                if not values.get("signed_at"):
                    values["signed_at"] = self.signed_at_for(values.get("doc_date"))
            keys = {"section": values.pop("section"), "title": values.pop("title")}
            doc, _ = Document.objects.update_or_create(**keys, defaults=values)
            if self.make_pdf and not doc.file and not doc.url:
                content = generate_demo_pdf(
                    doc.title,
                    org_name=self.org.full_name if self.org else "",
                    number=doc.number,
                    doc_date=doc.doc_date,
                    signer=doc.signer if doc.signed else "",
                    signed_at=doc.signed_at,
                )
                self.save_file(doc, "file", f"{DEMO_PREFIX}doc-{doc.pk}.pdf", content)
        self.stdout.write(f"  документы: {len(rows)}")

    def load_teachers(self, rows):
        for index, row in enumerate(rows, start=1):
            values = model_values(Teacher, row)
            values.setdefault("order", index)
            fio = values.pop("fio")
            teacher, _ = Teacher.objects.update_or_create(fio=fio, defaults=values)
            slugs = row.get("programs", [])
            programs = list(Program.objects.filter(slug__in=slugs))
            unknown = set(slugs) - {p.slug for p in programs}
            if unknown:
                self.stderr.write(self.style.WARNING(f"  {fio}: неизвестные программы {sorted(unknown)}"))
            teacher.programs.set(programs)
        self.stdout.write(f"  педагогический состав: {len(rows)}")

    def load_vacant(self, rows):
        for row in rows:
            program = Program.objects.filter(slug=row.get("program")).first()
            if program is None:
                self.stderr.write(self.style.WARNING(f"  вакантные места: нет программы {row.get('program')}"))
                continue
            VacantPlace.objects.update_or_create(program=program, defaults=model_values(VacantPlace, row))
        self.stdout.write(f"  вакантные места: {len(rows)}")

    # --- PDF ------------------------------------------------------------------
    def get_default_signer(self):
        head = Manager.objects.filter(role="head").first()
        if head is None:
            return "Руководитель организации"
        parts = head.fio.split()
        short = parts[0] + (" " + " ".join(f"{p[0]}." for p in parts[1:3]) if len(parts) > 1 else "")
        return f"{short}, {head.post.lower()}"

    @staticmethod
    def signed_at_for(doc_date):
        """Дата подписи по умолчанию — дата документа, 10:00 по времени сайта."""
        day = doc_date or timezone.localdate()
        return timezone.make_aware(datetime.combine(day, time(10, 0)))

    def save_file(self, obj, field_name, filename, content):
        """Сохранить PDF под постоянным именем (старый демо-файл с тем же именем заменяется)."""
        field = getattr(obj, field_name)
        upload_to = obj._meta.get_field(field_name).upload_to
        name = f"{upload_to.rstrip('/')}/{filename}"
        if field.storage.exists(name):
            field.storage.delete(name)
        field.save(filename, ContentFile(content), save=False)
        type(obj).objects.filter(pk=obj.pk).update(**{field_name: field.name})
        self.written_files.add(Path(field.path).resolve())
        self.pdf_count += 1

    def generate_program_files(self):
        org_name = self.org.full_name if self.org else ""
        for program in Program.objects.all():
            for field_name, label in PROGRAM_FILES:
                if getattr(program, field_name):
                    continue
                content = generate_demo_pdf(
                    f"{label}: «{program.title}»",
                    org_name=org_name,
                    signer=self.default_signer,
                    signed_at=self.signed_at_for(None),
                    body=(
                        f"{label} по программе «{program.title}» ({program.get_kind_display().lower()}), "
                        f"объём {program.hours} ч, форма обучения: {program.form}. "
                        "Демонстрационный файл: на рабочем сайте здесь размещается утверждённый документ."
                    ),
                )
                self.save_file(program, field_name, f"{DEMO_PREFIX}{program.slug}-{field_name}.pdf", content)
                setattr(program, field_name, getattr(program, field_name).name)

    def generate_department_clauses(self, departments):
        """Демо-PDF «Положение о <подразделении>» для подразделений без файла положения."""
        org_name = self.org.full_name if self.org else ""
        for department in departments:
            if department.clause_file:
                continue
            title = f"Положение о подразделении «{department.name}»"
            content = generate_demo_pdf(
                title,
                org_name=org_name,
                signer=self.default_signer,
                signed_at=self.signed_at_for(None),
                body=(
                    f"Положение определяет задачи, функции и порядок работы подразделения «{department.name}». "
                    "Демонстрационный файл: на рабочем сайте здесь размещается утверждённое положение."
                ),
            )
            self.save_file(department, "clause_file", f"{DEMO_PREFIX}clause-{department.pk}.pdf", content)

    # --- администратор ------------------------------------------------------
    def create_admin(self):
        password = os.environ.get("DEMO_ADMIN_PASSWORD", "")
        if not password:
            self.stdout.write("DEMO_ADMIN_PASSWORD не задан — пользователь admin не создаётся.")
            return
        User = get_user_model()
        try:
            validate_password(password, user=User(username="admin"))
        except ValidationError as exc:
            problems = " ".join(exc.messages)
            if not settings.SITE_DEMO:
                self.stderr.write(
                    self.style.ERROR(
                        f"DEMO_ADMIN_PASSWORD слишком простой: {problems} Пользователь admin НЕ создан. "
                        "Задайте надёжный пароль (12+ символов, буквы и цифры) или создайте "
                        "пользователя командой: python manage.py createsuperuser"
                    )
                )
                return
            self.stderr.write(self.style.WARNING(f"Внимание: DEMO_ADMIN_PASSWORD слабый ({problems}) — только для демо."))
        user, created = User.objects.get_or_create(username="admin", defaults={"email": ""})
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()
        self.stdout.write(f"Пользователь admin {'создан' if created else 'обновлён'}.")
