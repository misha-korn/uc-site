"""
Регрессионные тесты на исправления по итогам ревью (code-reviewer, qa-security,
legal-compliance, business-analyst). Каждый тест падал до соответствующего исправления.
"""

import csv
import io
import logging
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.admin import csv_safe
from core.context_processors import REQUEST_ORG_ATTR, site
from core.forms import MSG_PHONE_INVALID, LeadForm, normalize_phone
from core.models import Lead, Program, ProgramCategory
from core.views import mask_ip, parse_program_id
from sveden.models import SECTIONS, Department, EduPlace, Founder, Manager, Organization, Teacher, VacantPlace

from .helpers import make_category, make_org, make_program, with_stub_templates

BASE_DIR = Path(settings.BASE_DIR)


def lead_data(**extra):
    data = {
        "name": "Иван",
        "phone": "+7 900 123-45-67",
        "email": "",
        "organization": "",
        "program": "",
        "comment": "",
        "listeners": "",
        "consent": "on",
        "website": "",
    }
    data.update(extra)
    return data


# --- 1. HEAD-запросы ------------------------------------------------------------

@with_stub_templates
class HeadRequestsTests(TestCase):
    """require_safe вместо require_GET: HEAD (мониторинги, проверки ссылок) не должен давать 405."""

    @classmethod
    def setUpTestData(cls):
        make_org()
        make_program(make_category(), slug="head-p")

    def test_head_on_every_public_page(self):
        urls = [
            "/", "/obuchenie/", "/obuchenie/head-p/", "/kontakty/", "/politika/", "/soglasie/",
            "/zayavka/", "/zayavka/spasibo/", "/robots.txt", "/sveden/",
        ] + [f"/sveden/{slug}/" for slug, _ in SECTIONS]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.head(url).status_code, 200)

    def test_post_still_not_allowed_on_pages(self):
        self.assertEqual(self.client.post("/sveden/common/").status_code, 405)
        self.assertEqual(self.client.post("/robots.txt").status_code, 405)


# --- 2, 11, 13. Заявки в админке: CSV, новые поля, журнал ------------------------

class LeadAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("boss", "b@example.com", "Boss-Strong-2026")

    def setUp(self):
        self.client.force_login(self.admin)

    def export(self, *leads):
        response = self.client.post(
            "/admin/core/lead/", {"action": "export_csv", "_selected_action": [lead.pk for lead in leads]}
        )
        return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))

    def test_csv_safe_unit(self):
        for raw in ("=1+1", "+7900", "-2", "@SUM(A1)", "\tx", "\rx"):
            self.assertEqual(csv_safe(raw), "'" + raw)
        self.assertEqual(csv_safe("Иван"), "Иван")
        self.assertEqual(csv_safe(None), "")
        self.assertEqual(csv_safe(5), 5)

    def test_csv_has_listeners_and_invoice_and_escapes_tab(self):
        lead = Lead.objects.create(
            name="\t=evil", phone="+79001234567", consent=True, listeners=25, need_invoice=True, organization="@org"
        )
        header, row = self.export(lead)
        data = dict(zip(header, row))
        self.assertEqual(data["Слушателей"], "25")
        self.assertEqual(data["Нужен счёт/КП"], "да")
        self.assertEqual(data["Имя"], "'\t=evil")
        self.assertEqual(data["Организация"], "'@org")

    def test_admin_change_page_shows_new_fields(self):
        lead = Lead.objects.create(name="Иван", phone="+79001234567", consent=True)
        html = self.client.get(f"/admin/core/lead/{lead.pk}/change/").content.decode()
        self.assertIn('name="listeners"', html)
        self.assertIn('name="need_invoice"', html)

    def test_str_and_admin_log_without_name(self):
        lead = Lead.objects.create(name="Секретов Секрет", phone="+79001234567", consent=True)
        self.assertEqual(str(lead), f"Заявка #{lead.pk}")
        self.client.post(
            f"/admin/core/lead/{lead.pk}/change/",
            {"status": "work", "staff_note": "", "name": lead.name, "phone": lead.phone, "email": "",
             "organization": "", "program": "", "listeners": "", "comment": ""},
        )
        entry = LogEntry.objects.get()
        self.assertEqual(entry.object_repr, f"Заявка #{lead.pk}")
        self.assertNotIn("Секрет", entry.object_repr)

    def test_category_changelist_no_n_plus_one(self):
        def count_queries():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get("/admin/core/programcategory/").status_code, 200)
            return len(ctx.captured_queries)

        cat = make_category(slug="c0")
        make_program(cat, slug="p0")
        one = count_queries()
        for i in range(1, 5):
            make_program(make_category(slug=f"c{i}", name=f"Направление {i}"), slug=f"p{i}")
        self.assertEqual(count_queries(), one)

    def test_category_changelist_shows_count(self):
        cat = make_category(slug="cnt")
        make_program(cat, slug="cnt-1")
        make_program(cat, slug="cnt-2", is_published=False)
        obj = ProgramCategory.objects.get(slug="cnt")
        from core.admin import ProgramCategoryAdmin
        from django.contrib import admin as dj_admin

        model_admin = ProgramCategoryAdmin(ProgramCategory, dj_admin.site)
        request = RequestFactory().get("/")
        request.user = self.admin
        annotated = model_admin.get_queryset(request).get(pk=obj.pk)
        self.assertEqual(model_admin.programs_total(annotated), 2)


# --- 3. ?program= с юникод-цифрами -------------------------------------------------

class ProgramParamTests(TestCase):
    def test_parse_program_id(self):
        self.assertEqual(parse_program_id("12"), 12)
        self.assertEqual(parse_program_id(" 7 "), 7)
        for bad in ("²", "١٢", "1_0", "+5", "-1", "0", "abc", "", None):
            self.assertIsNone(parse_program_id(bad), bad)


# --- 4. Проверка загружаемых файлов ------------------------------------------------

class UploadValidationTests(TestCase):
    def assertRejected(self, obj, field):
        with self.assertRaises(ValidationError) as ctx:
            obj.full_clean()
        self.assertIn(field, ctx.exception.message_dict)

    def assertAccepted(self, obj, field):
        try:
            obj.full_clean()
        except ValidationError as exc:
            self.assertNotIn(field, exc.message_dict)

    def test_program_files_only_documents(self):
        program = Program(
            category=make_category(), title="T", slug="t", hours=1, duration="1", price=1,
            document_issued="Д", short="к", description="о", disciplines="м",
        )
        program.op_file = SimpleUploadedFile("evil.svg", b"<svg onload=alert(1)>")
        self.assertRejected(program, "op_file")
        program.op_file = SimpleUploadedFile("op.pdf", b"%PDF-1.4")
        program.plan_file = SimpleUploadedFile("plan.docx", b"PK")
        program.rpd_file = SimpleUploadedFile("rpd.pdf.sig", b"sig")
        program.full_clean()

    def test_manager_photo_only_images(self):
        manager = Manager(role="head", fio="Ф", post="Д", photo=SimpleUploadedFile("x.html", b"<script>"))
        self.assertRejected(manager, "photo")
        manager.photo = SimpleUploadedFile("face.webp", b"RIFF")
        manager.full_clean()

    def test_department_clause_and_org_license(self):
        self.assertRejected(Department(name="Д", clause_file=SimpleUploadedFile("a.js", b"x")), "clause_file")
        org = Organization(
            full_name="Ф", short_name="К", reg_date="2014-01-01", address="а", work_time="в", phones="1",
            emails="e@e.ru", inn="1", ogrn="1", license_number="1", license_issuer="м",
            license_file=SimpleUploadedFile("lic.htm", b"<b>"),
        )
        self.assertRejected(org, "license_file")

    def test_size_limit_20mb(self):
        big = SimpleUploadedFile("big.pdf", b"%PDF")
        big.size = 20 * 1024 * 1024 + 1
        self.assertRejected(Department(name="Д", clause_file=big), "clause_file")
        ok = SimpleUploadedFile("ok.pdf", b"%PDF")
        ok.size = 20 * 1024 * 1024
        Department(name="Д", clause_file=ok).full_clean()


# --- 5, 6. Настройки входа, .env.example, nginx ----------------------------------------

class DeployFilesTests(TestCase):
    def read(self, rel):
        return (BASE_DIR / rel).read_text(encoding="utf-8")

    def test_env_example_defaults(self):
        env = self.read(".env.example")
        lines = [line.strip() for line in env.splitlines() if line.strip() and not line.startswith("#")]
        self.assertIn("SITE_DEMO=0", lines)
        self.assertIn("1 — только для демо-стенда", env)
        for line in ("LEAD_RETENTION_DAYS=365", "LEAD_SPAM_RETENTION_DAYS=30", "CSP_REPORT_ONLY=0", "MEDIA_ROOT="):
            self.assertIn(line, lines)

    def test_security_headers_snippet_no_duplicates(self):
        snippet = self.read("deploy/nginx/snippets/security-headers.conf")
        self.assertNotIn("add_header Permissions-Policy", snippet)
        self.assertNotIn("unsafe-inline", snippet)

    def test_nginx_login_rate_limit(self):
        for rels in (("deploy/nginx/uc-site.conf",), ("deploy/nginx/docker/common.conf", "deploy/nginx/docker/locations.conf")):
            with self.subTest(conf=rels):
                conf = "\n".join(self.read(rel) for rel in rels)
                self.assertIn("limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;", conf)
                self.assertIn("location = /admin/login/ {", conf)
                self.assertIn("limit_req zone=login burst=5 nodelay;", conf)

    def test_login_redirect_url(self):
        self.assertEqual(settings.LOGIN_REDIRECT_URL, "/admin/")

    def test_hsts_preload_off_by_default(self):
        env = {
            **os.environ, "DEBUG": "0", "SECRET_KEY": "test-" + "k" * 50, "ALLOWED_HOSTS": "example.com",
            "SECURE_SSL_REDIRECT": "1", "SITE_URL": "https://example.com", "SITE_DEMO": "0",
            "SKIP_DOTENV": "1",  # не читать локальный .env разработчика
        }
        env.pop("SECURE_HSTS_PRELOAD", None)
        code = "import django; django.setup(); from django.conf import settings; print(settings.SECURE_HSTS_PRELOAD)"
        out = subprocess.run(
            [sys.executable, "-c", code], cwd=BASE_DIR, env={**env, "DJANGO_SETTINGS_MODULE": "config.settings"},
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(out.stdout.strip(), "False")


# --- 8, 10, 14, 15. Сведения: вакантные места, места ГИА, педагоги, ссылки ------------

@with_stub_templates
class SvedenFixesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_org()
        cls.cat = make_category()

    def test_new_program_without_vacant_record_is_listed_with_zeros(self):
        with_record = make_program(self.cat, slug="vac-a", order=1)
        VacantPlace.objects.create(program=with_record, paid=7)
        fresh = make_program(self.cat, slug="vac-b", order=2)
        make_program(self.cat, slug="vac-hidden", order=3, is_published=False)
        vacancies = self.client.get("/sveden/vacant/").context["vacancies"]
        self.assertEqual([v.program.slug for v in vacancies], ["vac-a", "vac-b"])
        self.assertEqual(vacancies[0].paid, 7)
        self.assertEqual((vacancies[1].fed, vacancies[1].sub, vacancies[1].mest, vacancies[1].paid), (0, 0, 0, 0))
        self.assertEqual(vacancies[1].program, fresh)

    def test_vacant_place_unique_per_program(self):
        program = make_program(self.cat, slug="vac-u")
        VacantPlace.objects.create(program=program)
        with self.assertRaises(IntegrityError), transaction.atomic():
            VacantPlace.objects.create(program=program)

    def test_vacant_queries_do_not_grow(self):
        for i in range(3):
            make_program(self.cat, slug=f"vq-{i}")
        with CaptureQueriesContext(connection) as ctx:
            vacancies = self.client.get("/sveden/vacant/").context["vacancies"]
            [v.program.category.name for v in vacancies]
        few = len(ctx.captured_queries)
        for i in range(3, 8):
            make_program(self.cat, slug=f"vq-{i}")
        with CaptureQueriesContext(connection) as ctx:
            vacancies = self.client.get("/sveden/vacant/").context["vacancies"]
            [v.program.category.name for v in vacancies]
        self.assertEqual(len(ctx.captured_queries), few)

    def test_gia_place_itemprop(self):
        place = EduPlace.objects.create(kind="gia", address="г. Самара")
        place.full_clean()
        self.assertEqual(place.itemprop, "addressPlaceGia")

    def test_employees_only_published_programs(self):
        teacher = Teacher.objects.create(fio="Т", post="П", disciplines="д", level="у", qualification="к")
        teacher.programs.add(make_program(self.cat, slug="emp-pub"), make_program(self.cat, slug="emp-hid", is_published=False))
        teachers = self.client.get("/sveden/employees/").context["teachers"]
        with self.assertNumQueries(0):
            self.assertEqual([p.slug for p in teachers[0].programs.all()], ["emp-pub"])

    def test_website_fields_only_http(self):
        for bad in ("javascript:alert(1)", "ftp://files.example.ru", "example.ru"):
            with self.subTest(url=bad):
                with self.assertRaises(ValidationError):
                    Founder(name="У", website=bad).full_clean()
                with self.assertRaises(ValidationError):
                    Department(name="Д", site=bad).full_clean()
        Founder(name="У", website="https://example.ru").full_clean()
        Department(name="Д", site="http://example.ru/otdel").full_clean()

    def test_organization_loaded_once_on_sveden_page(self):
        with CaptureQueriesContext(connection) as ctx:
            self.client.get("/sveden/common/")
        org_queries = [q for q in ctx.captured_queries if 'FROM "sveden_organization"' in q["sql"]]
        self.assertEqual(len(org_queries), 1, org_queries)


# --- 11, 12, 19. Форма заявки -------------------------------------------------------

class LeadFormFixesTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_listeners_bounds(self):
        for bad in ("0", "501", "abc", "-3", "2.5"):
            with self.subTest(listeners=bad):
                form = LeadForm(lead_data(listeners=bad))
                self.assertFalse(form.is_valid())
                self.assertIn("listeners", form.errors)
        for good in ("", "1", "500"):
            with self.subTest(listeners=good):
                self.assertTrue(LeadForm(lead_data(listeners=good)).is_valid())

    def test_new_fields_saved(self):
        response = self.client.post("/zayavka/", lead_data(listeners="25", need_invoice="on"))
        self.assertEqual(response.status_code, 302)
        lead = Lead.objects.get()
        self.assertEqual(lead.listeners, 25)
        self.assertTrue(lead.need_invoice)

    def test_new_fields_optional(self):
        data = lead_data()
        data.pop("listeners")
        self.assertEqual(self.client.post("/zayavka/", data).status_code, 302)
        lead = Lead.objects.get()
        self.assertIsNone(lead.listeners)
        self.assertFalse(lead.need_invoice)

    def test_listeners_model_validators(self):
        lead = Lead(name="И", phone="+79001234567", listeners=501)
        with self.assertRaises(ValidationError):
            lead.full_clean()

    def test_phone_normalized(self):
        cases = {
            "+7 (900) 123-45-67": "+79001234567",
            "8 900 123 45 67": "+79001234567",
            "89001234567": "+79001234567",
            "900 123-45-67": "+79001234567",
            "8 (846) 000-12-34": "+78460001234",
            "+375 29 123 45 67": "+375291234567",
            "+49 30 1234 5678": "+493012345678",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_phone(raw), expected)
                form = LeadForm(lead_data(phone=raw))
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data["phone"], expected)

    def test_phone_garbage_rejected(self):
        for raw in ("+7 900 123.45.67", "7+9001234567", "+7 900 123-45-67 доб", "+7 900 123-45-67 #1",
                    "+7 (900) 123 - 45 - 67 - 0", "+7/900/1234567"):
            with self.subTest(raw=raw):
                form = LeadForm(lead_data(phone=raw))
                self.assertFalse(form.is_valid())
                self.assertIn(MSG_PHONE_INVALID, form.errors["phone"])

    def test_phone_saved_normalized(self):
        self.client.post("/zayavka/", lead_data(phone="8 (900) 123-45-67"))
        self.assertEqual(Lead.objects.get().phone, "+79001234567")


# --- 16. IP в журнале -------------------------------------------------------------------

class MaskIpTests(TestCase):
    def test_mask_ip(self):
        self.assertEqual(mask_ip("10.9.9.9"), "10.9.9.x")
        self.assertEqual(mask_ip("2001:db8:85a3::8a2e:370:7334"), "2001:db8:85a3::x")
        self.assertEqual(mask_ip(None), "unknown")
        self.assertEqual(mask_ip("bad"), "invalid")

    def test_logs_contain_masked_ip_only(self):
        cache.clear()
        with self.assertLogs("core.views", level=logging.INFO) as logs:
            self.client.post("/zayavka/", lead_data(website="http://spam"), REMOTE_ADDR="10.9.8.7")
            for i in range(6):
                self.client.post("/zayavka/", lead_data(name=f"Иван {i}"), REMOTE_ADDR="10.9.8.7")
        output = "\n".join(logs.output)
        self.assertIn("10.9.8.x", output)
        self.assertNotIn("10.9.8.7", output)


# --- 18, 21. Контекст-процессор: canonical_url и Organization ---------------------------

class ContextProcessorTests(TestCase):
    def test_canonical_url_from_site_url(self):
        request = RequestFactory().get("/obuchenie/?cat=x&utm=1")
        with override_settings(SITE_URL="https://uc.example.ru/"):
            self.assertEqual(site(request)["canonical_url"], "https://uc.example.ru/obuchenie/")
        with override_settings(SITE_URL=""):
            self.assertEqual(site(request)["canonical_url"], "http://testserver/obuchenie/")

    def test_org_taken_from_request_without_query(self):
        org = make_org()
        request = RequestFactory().get("/")
        setattr(request, REQUEST_ORG_ATTR, org)
        with CaptureQueriesContext(connection) as ctx:
            context = site(request)
        self.assertIs(context["org"], org)
        self.assertFalse([q for q in ctx.captured_queries if "sveden_organization" in q["sql"]])

    def test_org_none_from_request_kept(self):
        make_org()
        request = RequestFactory().get("/")
        setattr(request, REQUEST_ORG_ATTR, None)
        self.assertIsNone(site(request)["org"])
        self.assertIsNotNone(site(RequestFactory().get("/"))["org"])
