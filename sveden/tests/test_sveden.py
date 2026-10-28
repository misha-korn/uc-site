"""Тесты раздела «Сведения»: контекст страниц, page_updated, singleton, админка, seed_demo, PDF."""

import json
import os
import shutil
import tempfile
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from unittest import mock, skipUnless

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Program, ProgramCategory
from core.tests.helpers import make_category, make_org, make_program, with_stub_templates
from sveden import demo_pdf
from sveden.models import (
    SECTIONS,
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
from sveden.views import NO_PRESCRIPTIONS_TEXT, compute_page_updated


@with_stub_templates
class SvedenContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cat = make_category()
        cls.program = make_program(cat, slug="ot-a")
        cls.hidden = make_program(cat, slug="hidden", is_published=False)
        Founder.objects.create(name="Учредитель")
        EduPlace.objects.create(kind="oppo", address="Адрес мастерской")
        Department.objects.create(name="Учебная часть")
        Document.objects.create(section="document", itemprop="ustavDocLink", title="Устав", url="https://e.ru/u.pdf")
        Document.objects.create(section="document", title="Скрытый", is_published=False)
        Document.objects.create(section="struct", itemprop="divisionClauseDocLink", title="Положение")
        Manager.objects.create(role="head", fio="Романова И.В.", post="Директор")
        Manager.objects.create(role="zam", fio="Зам Один", post="Заместитель", order=1)
        Manager.objects.create(role="zam", fio="Зам Два", post="Заместитель", order=2)
        teacher = Teacher.objects.create(fio="Соколова Е.В.", post="Преподаватель", disciplines="ОТ", level="Высшее", qualification="2025")
        teacher.programs.add(cls.program)
        Facility.objects.create(kind="cab", name="Кабинет 1", address="ул. Учебная", equipment="Проектор")
        VacantPlace.objects.create(program=cls.program, paid=10)
        VacantPlace.objects.create(program=cls.hidden, paid=3)
        SvedenField.objects.create(page="budget", itemprop="finPost", label="Поступления", value="1 000 000")
        SvedenField.objects.create(page="grants", itemprop="", label="Стипендии", value="Не предусмотрены")

    def get(self, name):
        return self.client.get(reverse(f"sveden:{name}")).context

    def test_every_section_has_section_and_page_updated(self):
        for slug, title in SECTIONS:
            with self.subTest(slug=slug):
                ctx = self.get(slug)
                self.assertEqual(ctx["section"]["slug"], slug)
                self.assertEqual(ctx["section"]["title"], title)
                self.assertEqual(ctx["section"]["url"], f"/sveden/{slug}/")
                self.assertIsInstance(ctx["page_updated"], date)
                self.assertEqual(len(ctx["sveden_sections"]), 14)

    def test_index(self):
        ctx = self.get("index")
        self.assertEqual([s["slug"] for s in ctx["sections"]], [slug for slug, _ in SECTIONS])
        self.assertEqual(ctx["sections"][4]["slug"], "eduStandarts")

    def test_common(self):
        ctx = self.get("common")
        self.assertEqual(ctx["org"], self.org)
        self.assertEqual(len(ctx["founders"]), 1)
        self.assertEqual(ctx["places"][0].itemprop, "addressPlaceOppo")

    def test_struct_and_document(self):
        ctx = self.get("struct")
        self.assertEqual([d.title for d in ctx["docs"]], ["Положение"])
        self.assertEqual(len(ctx["departments"]), 1)
        ctx = self.get("document")
        self.assertEqual([d.title for d in ctx["docs"]], ["Устав"])  # без неопубликованного
        self.assertEqual(ctx["docs"][0].link, "https://e.ru/u.pdf")
        self.assertEqual(ctx["prescriptions_text"], NO_PRESCRIPTIONS_TEXT)

    def test_education_paid_vacant(self):
        self.assertEqual([p.slug for p in self.get("education")["programs"]], ["ot-a"])
        self.assertEqual([p.slug for p in self.get("paid_edu")["programs"]], ["ot-a"])
        vacancies = self.get("vacant")["vacancies"]
        self.assertEqual([v.program.slug for v in vacancies], ["ot-a"])

    def test_managers(self):
        ctx = self.get("managers")
        self.assertEqual(ctx["head"].fio, "Романова И.В.")
        self.assertEqual(ctx["head"].itemprop, "rucovodstvo")
        self.assertEqual([m.fio for m in ctx["deputies"]], ["Зам Один", "Зам Два"])

    def test_employees_prefetched(self):
        teachers = self.get("employees")["teachers"]
        with self.assertNumQueries(0):
            self.assertEqual([p.slug for p in teachers[0].programs.all()], ["ot-a"])

    def test_fields_pages(self):
        self.assertEqual([f.label for f in self.get("budget")["fields"]], ["Поступления"])
        self.assertEqual([f.label for f in self.get("grants")["fields"]], ["Стипендии"])
        self.assertEqual(self.get("objects")["facilities"][0].name, "Кабинет 1")
        for slug in ("eduStandarts", "inter", "catering", "budget", "grants", "objects", "paid_edu", "education"):
            self.assertIsInstance(self.get(slug)["docs"], list)

    def test_page_updated_from_data(self):
        old = timezone.now() - timedelta(days=30)
        Organization.objects.filter(pk=1).update(updated_at=old)
        Manager.objects.update(updated_at=old - timedelta(days=5))
        self.assertEqual(self.get("managers")["page_updated"], timezone.localtime(old - timedelta(days=5)).date())
        # Страница без своих данных — дата изменения Организации.
        self.assertEqual(self.get("catering")["page_updated"], timezone.localtime(old).date())


class PageUpdatedUnitTests(TestCase):
    def test_no_data_no_org_is_today(self):
        self.assertEqual(compute_page_updated(None, []), timezone.localdate())


@with_stub_templates
class EmptySvedenTests(TestCase):
    def test_no_org_document_page(self):
        ctx = self.client.get("/sveden/common/").context
        self.assertIsNone(ctx["org"])
        self.assertEqual(ctx["founders"], [])
        self.assertIsNone(self.client.get("/sveden/managers/").context["head"])


class OrganizationSingletonTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("boss", "b@example.com", "pass12345")
        self.client.force_login(self.admin)

    def test_model_singleton(self):
        make_org()
        org2 = Organization(full_name="Другая", short_name="Д", reg_date=date(2020, 1, 1), address="a",
                            work_time="w", phones="p", emails="e", inn="1", ogrn="2", license_number="3",
                            license_issuer="4")
        org2.save()
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(Organization.load().short_name, "Д")

    def test_admin_singleton(self):
        response = self.client.get("/admin/sveden/organization/")
        self.assertRedirects(response, "/admin/sveden/organization/add/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/admin/sveden/organization/add/").status_code, 200)
        make_org()
        response = self.client.get("/admin/sveden/organization/")
        self.assertRedirects(response, "/admin/sveden/organization/1/change/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/admin/sveden/organization/add/").status_code, 403)
        self.assertEqual(self.client.get("/admin/sveden/organization/1/delete/").status_code, 403)
        self.assertEqual(self.client.get("/admin/sveden/organization/1/change/").status_code, 200)

    def test_all_admin_pages_open(self):
        make_org()
        program = make_program(make_category())
        for model in ("founder", "eduplace", "department", "document", "manager", "teacher",
                      "facility", "vacantplace", "svedenfield"):
            with self.subTest(model=model):
                self.assertEqual(self.client.get(f"/admin/sveden/{model}/").status_code, 200)
                self.assertEqual(self.client.get(f"/admin/sveden/{model}/add/").status_code, 200)
        for url in ("/admin/core/program/", "/admin/core/programcategory/",
                    f"/admin/core/program/{program.pk}/change/", "/admin/core/program/add/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_document_itemprop_hints_and_free_value(self):
        response = self.client.get("/admin/sveden/document/add/")
        self.assertContains(response, '<datalist id="itemprop-hints">')
        self.assertContains(response, 'value="ustavDocLink"')
        response = self.client.post("/admin/sveden/document/add/", {
            "section": "document", "title": "Свой документ", "itemprop": "myOwnItemprop",
            "url": "https://e.ru/x.pdf", "order": 0, "is_published": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Document.objects.get().itemprop, "myOwnItemprop")


MINI_SEED = {
    "organization": {
        "full_name": "АНО ДПО «Тестовый центр»", "short_name": "АНО ДПО «ТЦ»", "reg_date": "2014-03-12",
        "address": "г. Самара", "work_time": "Пн–Пт", "phones": "+7 846 000-00-00", "emails": "t@e.ru",
        "inn": "6300000000", "ogrn": "1146300000000", "license_number": "Л035-1", "license_date": "2014-09-25",
        "license_issuer": "Минобр", "license_url": "https://islod.obrnadzor.gov.ru/rlic/", "map_embed_url": "",
    },
    "founders": [{"name": "Учредитель", "address": "г. Самара", "phone": "", "email": "", "website": "", "order": 1}],
    "edu_places": [{"kind": "dop", "address": "ул. Учебная, 7", "order": 5}],
    "categories": [{"name": "Охрана труда", "slug": "ot", "short": "", "icon": "shield", "order": 1}],
    "programs": [{
        "category": "ot", "title": "Охрана труда А", "slug": "ot-a", "kind": "ot", "code": "", "hours": 16,
        "duration": "2 дня", "form": "Очная", "price": 2500, "document_issued": "Протокол", "short": "к",
        "description": "о", "audience": "", "disciplines": "М1\nМ2", "practice": "", "is_popular": True, "order": 1,
    }],
    "departments": [{"name": "Учебная часть", "head_fio": "Иванов", "head_post": "Начальник", "address": "",
                     "site": "", "email": "", "order": 3}],
    "documents": [
        {"section": "document", "itemprop": "ustavDocLink", "title": "Устав организации", "number": "1",
         "doc_date": "2023-02-20", "signed": True, "signer": "Романова И. В., директор", "order": 1},
        {"section": "document", "itemprop": "localActStud", "title": "Правила для обучающихся", "number": "",
         "doc_date": None, "signed": True, "order": 2},
    ],
    "managers": [{"role": "head", "fio": "Романова Ирина Владимировна", "post": "Директор", "phone": "",
                  "email": "", "order": 1}],
    "teachers": [{"fio": "Соколова Е.В.", "post": "Преподаватель", "disciplines": "ОТ", "level": "Высшее",
                  "degree": "Нет", "academic_title": "Нет", "qualification": "2025", "retraining": "",
                  "experience": 18, "programs": ["ot-a", "net-takoi"], "order": 1}],
    "facilities": [
        {"kind": "cab", "name": "Кабинет 1", "address": "ул. Учебная", "equipment": "Проектор", "ovz": "Да", "order": 2},
        {"kind": "sport", "name": "Отсутствует", "address": "Отсутствует", "equipment": "Отсутствует",
         "ovz": "Отсутствует", "order": 8},
    ],
    "vacant": [{"program": "ot-a", "fed": 0, "sub": 0, "mest": 0, "paid": 12}],
    "fields": [
        {"page": "budget", "itemprop": "finPost", "label": "Поступления", "value": "1 000", "order": 1},
        {"page": "grants", "itemprop": "", "label": "Без itemprop", "value": "Нет", "order": 2},
    ],
}


class SeedDemoTests(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="uc-seed-test-"))
        self.media = self.tmp / "media"
        self.seed_file = self.tmp / "seed.json"
        self.seed_file.write_text(json.dumps(MINI_SEED, ensure_ascii=False), encoding="utf-8")
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_seed(self, *args, env=None):
        out, err = StringIO(), StringIO()
        with mock.patch.dict(os.environ, env or {}, clear=False):
            if not env:
                os.environ.pop("DEMO_ADMIN_PASSWORD", None)
            call_command("seed_demo", "--file", str(self.seed_file), *args, stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    def test_seed_creates_everything_and_is_idempotent(self):
        out, err = self.run_seed()
        self.assertIn("Демо-данные загружены", out)
        self.assertIn("net-takoi", err)  # предупреждение о неизвестной программе
        counts = lambda: [m.objects.count() for m in (  # noqa: E731
            Organization, Founder, EduPlace, ProgramCategory, Program, Department, Document, Manager,
            Teacher, Facility, VacantPlace, SvedenField)]
        first = counts()
        self.assertEqual(first, [1, 1, 1, 1, 1, 1, 2, 1, 1, 2, 1, 2])
        self.run_seed()
        self.assertEqual(counts(), first)

        self.assertEqual(EduPlace.objects.get().order, 5)
        self.assertEqual(Department.objects.get().order, 3)
        self.assertEqual(Facility.objects.get(kind="sport").name, "Отсутствует")
        self.assertEqual(SvedenField.objects.get(page="grants").itemprop, "")
        self.assertEqual(Organization.load().license_date, date(2014, 9, 25))
        self.assertEqual(list(Teacher.objects.get().programs.values_list("slug", flat=True)), ["ot-a"])
        self.assertEqual(VacantPlace.objects.get().paid, 12)

        ustav = Document.objects.get(itemprop="ustavDocLink")
        self.assertTrue(ustav.signed)
        self.assertIsNotNone(ustav.signed_at)
        self.assertTrue(ustav.file.name.endswith(".pdf"))
        self.assertTrue((self.media / ustav.file.name).is_file())
        # Подписант по умолчанию — руководитель.
        self.assertEqual(Document.objects.get(itemprop="localActStud").signer, "Романова И. В., директор")

        program = Program.objects.get()
        for field in ("op_file", "plan_file", "schedule_file", "rpd_file", "methodology_file"):
            self.assertTrue((self.media / getattr(program, field).name).is_file(), field)
        # 2 документа + положение подразделения; без дублей после 2-го запуска.
        self.assertEqual(len(list((self.media / "docs").glob("*.pdf"))), 3)

    def test_reset(self):
        self.run_seed()
        Founder.objects.create(name="Лишний")
        self.run_seed("--reset", "--force")
        self.assertEqual(Founder.objects.count(), 1)
        self.assertEqual(Program.objects.count(), 1)

    def test_admin_user_from_env(self):
        self.run_seed("--no-pdf")
        self.assertFalse(get_user_model().objects.filter(username="admin").exists())
        self.run_seed("--no-pdf", env={"DEMO_ADMIN_PASSWORD": "S3cret-demo-pass"})
        user = get_user_model().objects.get(username="admin")
        self.assertTrue(user.is_superuser and user.is_staff)
        self.assertTrue(user.check_password("S3cret-demo-pass"))

    def test_department_clause_pdf_generated(self):
        self.run_seed()
        department = Department.objects.get()
        self.assertTrue(department.clause_file.name.startswith("docs/demo-clause-"))
        self.assertTrue((self.media / department.clause_file.name).is_file())
        # Повторный запуск не плодит файлы и не теряет ссылку.
        name = department.clause_file.name
        self.run_seed()
        self.assertEqual(Department.objects.get().clause_file.name, name)

    def test_reset_requires_force_outside_demo(self):
        from django.core.management.base import CommandError

        self.run_seed()
        with override_settings(SITE_DEMO=False), self.assertRaises(CommandError):
            self.run_seed("--reset")
        self.assertEqual(Program.objects.count(), 1)
        with override_settings(SITE_DEMO=True):
            self.run_seed("--reset")
        self.assertEqual(Program.objects.count(), 1)

    def test_reset_deletes_old_files_only_after_commit(self):
        self.run_seed()
        stale = self.media / "docs" / "demo-stale.pdf"
        stale.write_bytes(b"%PDF")
        ustav_name = Document.objects.get(itemprop="ustavDocLink").file.name
        # Загрузка падает (неизвестное направление) → транзакция откатывается → файлы на месте.
        broken = {**MINI_SEED, "programs": [{**MINI_SEED["programs"][0], "category": "net-takogo"}]}
        self.seed_file.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
        from django.core.management.base import CommandError

        with self.captureOnCommitCallbacks(execute=True), self.assertRaises(CommandError):
            self.run_seed("--reset", "--force")
        self.assertTrue(stale.is_file())
        self.assertTrue((self.media / ustav_name).is_file())
        # Успешный --reset: старые демо-файлы удалены, заново созданные — на месте.
        self.seed_file.write_text(json.dumps(MINI_SEED, ensure_ascii=False), encoding="utf-8")
        with self.captureOnCommitCallbacks(execute=True):
            self.run_seed("--reset", "--force")
        self.assertFalse(stale.exists())
        program = Program.objects.get()
        for field in ("op_file", "plan_file", "schedule_file", "rpd_file", "methodology_file"):
            self.assertTrue((self.media / getattr(program, field).name).is_file(), field)
        for doc in Document.objects.all():
            self.assertTrue((self.media / doc.file.name).is_file(), doc.title)
        self.assertTrue((self.media / Department.objects.get().clause_file.name).is_file())

    def test_weak_admin_password_rejected_outside_demo(self):
        with override_settings(SITE_DEMO=False):
            _, err = self.run_seed("--no-pdf", env={"DEMO_ADMIN_PASSWORD": "12345678"})
        self.assertIn("слишком простой", err)
        self.assertFalse(get_user_model().objects.filter(username="admin").exists())

    def test_weak_admin_password_warns_on_demo(self):
        with override_settings(SITE_DEMO=True):
            _, err = self.run_seed("--no-pdf", env={"DEMO_ADMIN_PASSWORD": "admin"})
        self.assertIn("слабый", err)
        self.assertTrue(get_user_model().objects.get(username="admin").check_password("admin"))

    def test_missing_file_error(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("seed_demo", "--file", str(self.tmp / "nope.json"), stdout=StringIO())

    @skipUnless(Path(__file__).resolve().parents[2].joinpath("seed", "demo_content.json").is_file(),
                "seed/demo_content.json ещё не создан")
    def test_real_seed_file_loads(self):
        real = Path(__file__).resolve().parents[2] / "seed" / "demo_content.json"
        call_command("seed_demo", "--file", str(real), "--no-pdf", stdout=StringIO(), stderr=StringIO())
        self.assertTrue(Organization.load())
        self.assertGreater(Program.objects.count(), 0)


@skipUnless(demo_pdf.find_font_path(), "Нет TTF-шрифта с кириллицей")
class DemoPdfTests(TestCase):
    def test_pdf_has_searchable_cyrillic_text(self):
        content = demo_pdf.generate_demo_pdf(
            "Устав организации", org_name="АНО ДПО «ТЦ»", number="1", doc_date=date(2023, 2, 20),
            signer="Романова И. В., директор",
        )
        self.assertTrue(content.startswith(b"%PDF"))
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("pypdf не установлен — проверка текста пропущена")
        from io import BytesIO

        text = PdfReader(BytesIO(content)).pages[0].extract_text()
        for needle in ("ДЕМО-ДОКУМЕНТ", "Устав организации", "простой электронной подписью",
                       "Романова И. В., директор", "20.02.2023"):
            self.assertIn(needle, text)

    @override_settings(PDF_FONT_PATH="/net/takogo/shrifta.ttf")
    def test_font_fallback(self):
        self.assertIsNotNone(demo_pdf.find_font_path())
