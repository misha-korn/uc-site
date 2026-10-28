"""
Регрессионные тесты QA (агент qa-security): граничные значения формы заявки,
XSS в выводе, снятие программы с публикации, страницы ошибок, CSV из админки.

Тесты на баги, которые ещё НЕ исправлены, помечены @unittest.expectedFailure —
после исправления декоратор нужно снять (иначе тест станет «unexpected success»).
"""

import csv
import io
import json
import re
import unittest

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, TestCase

from core.forms import MSG_COMMENT_TOO_LONG, MSG_NAME_TOO_LONG, MSG_PHONE_INVALID
from core.models import Lead
from sveden.models import Document

from .helpers import make_category, make_org, make_program

URL = "/zayavka/"
XSS = '<img src=x onerror=alert("xss")>QA'


def lead_data(**extra):
    data = {
        "name": "Иван",
        "phone": "+7 900 123-45-67",
        "email": "",
        "organization": "",
        "program": "",
        "comment": "",
        "consent": "on",
        "website": "",
    }
    data.update(extra)
    return data


class LeadBoundaryTests(TestCase):
    """Граничные значения формы заявки (проверены вручную на uvicorn, DEBUG=0)."""

    def setUp(self):
        cache.clear()

    def post(self, **extra):
        return self.client.post(URL, lead_data(**extra), REMOTE_ADDR="10.9.9.9")

    def assertSaved(self, response):
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["form"].errors)

    def assertFieldError(self, response, field, message=None):
        self.assertEqual(response.status_code, 200)
        errors = response.context["form"].errors
        self.assertIn(field, errors)
        if message:
            self.assertIn(message, errors[field])

    def test_name_length_120_ok_121_error(self):
        self.assertSaved(self.post(name="Я" * 120))
        self.assertFieldError(self.post(name="Я" * 121), "name", MSG_NAME_TOO_LONG)

    def test_name_only_spaces(self):
        self.assertFieldError(self.post(name="     "), "name")

    def test_comment_length_2000_ok_2001_error(self):
        self.assertSaved(self.post(comment="a" * 2000))
        self.assertFieldError(self.post(comment="a" * 2001), "comment", MSG_COMMENT_TOO_LONG)

    def test_emoji_saved_as_is(self):
        self.assertSaved(self.post(name="Иван 😀👍🏽", comment="Привет 🎉"))
        self.assertEqual(Lead.objects.get().name, "Иван 😀👍🏽")

    def test_script_in_name_rejected(self):
        self.assertFieldError(self.post(name="<script>alert(1)</script>"), "name")

    def test_script_and_sql_in_comment_stored_verbatim(self):
        payload = "<script>alert(1)</script>' OR 1=1; DROP TABLE core_lead;--"
        self.assertSaved(self.post(name="Robert'); DROP TABLE x;--", comment=payload))
        self.assertEqual(Lead.objects.get().comment, payload)

    def test_phone_digit_bounds(self):
        self.assertFieldError(self.post(phone="123456789"), "phone", MSG_PHONE_INVALID)  # 9 цифр
        self.assertFieldError(self.post(phone="1234567890123456"), "phone", MSG_PHONE_INVALID)  # 16 цифр
        self.assertFieldError(self.post(phone="+7 900 abc 45 67"), "phone", MSG_PHONE_INVALID)
        self.assertSaved(self.post(phone="123456789012345"))  # 15 цифр — можно

    def test_unknown_or_text_program_id(self):
        self.assertFieldError(self.post(program="999999"), "program")
        self.assertFieldError(self.post(program="abc"), "program")

    def test_null_byte_does_not_crash(self):
        response = self.post(name="Ив\x00ан")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Lead.objects.exists())

    def test_sixth_lead_rate_limited(self):
        for i in range(5):
            self.assertSaved(self.post(name=f"Иван {i}"))
        self.assertEqual(self.post(name="Шестой").status_code, 429)
        self.assertEqual(Lead.objects.count(), 5)

    def test_program_preselected_on_card_and_get_param(self):
        program = make_program(make_category(), slug="qa-pre")
        for url in (f"/obuchenie/{program.slug}/", f"{URL}?program={program.pk}"):
            html = self.client.get(url).content.decode()
            self.assertRegex(html, rf'<option value="{program.pk}" selected>', url)

    def test_get_form_with_unicode_digit_program(self):
        client = Client(raise_request_exception=False)
        self.assertEqual(client.get(URL + "?program=%C2%B2").status_code, 200)


class OutputEscapingTests(TestCase):
    """XSS: данные из админки выводятся экранированными, JSON-LD остаётся валидным."""

    @classmethod
    def setUpTestData(cls):
        make_org(full_name='АНО "Кавычки" </script><script>alert(1)</script>')
        cat = make_category(name=XSS)
        cls.program = make_program(
            cat,
            slug="qa-xss",
            title=XSS,
            short='Кратко "в кавычках" </script><script>alert(2)</script>',
            document_issued="</script><script>alert(3)</script>",
            description="<b>desc</b>\n\n<script>alert(4)</script>",
            disciplines="<i>m1</i>\nm2",
        )

    def test_pages_escape_admin_data(self):
        for url in ("/", "/obuchenie/", "/obuchenie/qa-xss/", "/sveden/education/", "/sveden/paid_edu/", URL):
            html = self.client.get(url).content.decode()
            self.assertNotIn("<img src=x", html, url)
            self.assertNotIn("<script>alert", html, url)

    def test_jsonld_valid(self):
        html = self.client.get("/obuchenie/qa-xss/").content.decode()
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        self.assertTrue(blocks)
        for block in blocks:
            json.loads(block)


class UnpublishTests(TestCase):
    def test_unpublished_program_hidden_everywhere(self):
        program = make_program(make_category(), slug="qa-hidden", title="Скрытая QA", is_published=False)
        self.assertEqual(self.client.get("/obuchenie/qa-hidden/").status_code, 404)
        for url in ("/", "/obuchenie/", "/sveden/education/", "/sitemap.xml", URL):
            self.assertNotIn("qa-hidden", self.client.get(url).content.decode(), url)
        cache.clear()
        response = self.client.post(URL, lead_data(program=program.pk))
        self.assertIn("program", response.context["form"].errors)


class ErrorPagesTests(TestCase):
    """При DEBUG=0 (тесты всегда идут с DEBUG=False) ошибки не раскрывают внутренности."""

    def test_404_custom_page(self):
        response = self.client.get("/net-takoy-stranicy/")
        self.assertEqual(response.status_code, 404)
        html = response.content.decode()
        self.assertIn("Страница не найдена", html)
        self.assertNotIn("Traceback", html)
        self.assertNotIn("urlpatterns", html)

    def test_500_page_has_no_details(self):
        from django.views.defaults import server_error

        response = server_error(RequestFactory().get("/"))
        html = response.content.decode()
        self.assertEqual(response.status_code, 500)
        self.assertIn("Что-то пошло не так", html)
        self.assertNotIn("Traceback", html)

    def test_media_path_traversal_blocked(self):
        client = Client(raise_request_exception=False)
        for url in ("/media/../config/settings.py", "/media/%2e%2e/config/settings.py", "/media/..%2fdb.sqlite3"):
            self.assertIn(client.get(url).status_code, (400, 404), url)

    def test_admin_requires_login(self):
        response = self.client.get("/admin/core/lead/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_head_requests_allowed(self):
        for url in ("/", "/sveden/common/", "/robots.txt"):
            self.assertEqual(self.client.head(url).status_code, 200, url)

    def test_csrf_failure_page_in_russian(self):
        response = Client(enforce_csrf_checks=True).post(URL, lead_data())
        self.assertEqual(response.status_code, 403)
        self.assertIn('lang="ru"', response.content.decode())


class AdminSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("qa-boss", "qa@example.com", "QaStrongPass-2026")

    def test_csv_export_neutralizes_formulas(self):
        lead = Lead.objects.create(
            name="=HYPERLINK(\"http://evil.example\",\"x\")", phone="+79001234567", consent=True,
            comment="=cmd|' /C calc'!A0",
        )
        self.client.force_login(self.admin)
        response = self.client.post("/admin/core/lead/", {"action": "export_csv", "_selected_action": [lead.pk]})
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))
        for cell in rows[1]:
            self.assertFalse(cell[:1] in ("=", "+", "-", "@"), cell)

    def test_document_rejects_html_upload(self):
        doc = Document(section="document", title="QA", file=SimpleUploadedFile("evil.html", b"<script>alert(1)</script>"))
        with self.assertRaises(ValidationError):
            doc.full_clean()

    def test_login_with_unsafe_next_stays_in_admin(self):
        response = self.client.post(
            "/admin/login/?next=//evil.example.com/",
            {"username": "qa-boss", "password": "QaStrongPass-2026", "next": "//evil.example.com/"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/admin/"), response["Location"])

    def test_login_never_redirects_offsite(self):
        response = self.client.post(
            "/admin/login/?next=https://evil.example.com/",
            {"username": "qa-boss", "password": "QaStrongPass-2026", "next": "https://evil.example.com/"},
        )
        self.assertNotIn("evil.example.com", response.get("Location", ""))
