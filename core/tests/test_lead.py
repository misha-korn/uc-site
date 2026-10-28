"""Тесты формы заявки: валидация, honeypot, rate-limit, CSRF, уведомления, админка."""

import asyncio
import json
import logging
from unittest import mock

import httpx
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import AsyncClient, Client, TestCase, override_settings
from django.urls import reverse

from core import notify
from core.forms import MSG_CONSENT_REQUIRED, MSG_PHONE_INVALID, LeadForm
from core.models import Lead

from .helpers import make_category, make_org, make_program, with_stub_templates

URL = "/zayavka/"


def valid_data(**extra):
    data = {
        "name": "Иван Петров",
        "phone": "+7 (900) 123-45-67",
        "email": "ivan@example.com",
        "organization": "ООО «Ромашка»",
        "program": "",
        "comment": "Нужно обучить 5 человек",
        "consent": "on",
        "website": "",
    }
    data.update(extra)
    return data


class LeadFormUnitTests(TestCase):
    def test_phone_validation(self):
        good = ["+7 (900) 123-45-67", "89001234567", "8 846 000 12 34", "+375 29 123 45 67"]
        bad = ["12345", "+7 900 12", "телефон", "+7 900 123 45 67 89 01 23", "89001234567<script>"]
        for phone in good:
            with self.subTest(phone=phone):
                self.assertTrue(LeadForm(valid_data(phone=phone)).is_valid())
        for phone in bad:
            with self.subTest(phone=phone):
                form = LeadForm(valid_data(phone=phone))
                self.assertFalse(form.is_valid())
                self.assertIn(MSG_PHONE_INVALID, form.errors["phone"])

    def test_required_and_lengths(self):
        form = LeadForm(valid_data(name="", phone="", consent=""))
        self.assertFalse(form.is_valid())
        self.assertEqual(set(form.errors), {"name", "phone", "consent"})
        self.assertFalse(LeadForm(valid_data(name="x" * 121)).is_valid())
        self.assertFalse(LeadForm(valid_data(comment="x" * 2001)).is_valid())
        self.assertFalse(LeadForm(valid_data(email="not-an-email")).is_valid())
        self.assertFalse(LeadForm(valid_data(name="http://spam.ru")).is_valid())
        self.assertTrue(LeadForm(valid_data(email="", organization="", comment="")).is_valid())

    def test_field_names_by_contract(self):
        self.assertEqual(
            list(LeadForm().fields),
            [
                "name", "phone", "email", "organization", "program", "comment",
                "listeners", "need_invoice", "consent", "website",
            ],
        )

    def test_consent_label_only_consent_link(self):
        """Согласие — отдельно от политики (156-ФЗ): в подписи чекбокса только ссылка на согласие."""
        label = str(LeadForm().fields["consent"].label)
        self.assertIn('href="/soglasie/"', label)
        self.assertNotIn('href="/politika/"', label)
        self.assertNotIn("политик", label.lower())

    def test_hidden_program_not_allowed(self):
        hidden = make_program(make_category(), slug="hidden", is_published=False)
        self.assertFalse(LeadForm(valid_data(program=hidden.pk)).is_valid())


@with_stub_templates
@override_settings(EMAIL_HOST="", TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID="")
class LeadCreateViewTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_valid_lead_created(self):
        program = make_program(make_category())
        response = self.client.post(URL, valid_data(program=program.pk), REMOTE_ADDR="10.1.2.3")
        self.assertRedirects(response, reverse("core:lead_success"), fetch_redirect_response=False)
        lead = Lead.objects.get()
        self.assertEqual(lead.name, "Иван Петров")
        self.assertEqual(lead.program, program)
        self.assertTrue(lead.consent)
        self.assertEqual(lead.consent_version, "1.0 от 27.10.2026")
        self.assertIsNotNone(lead.consent_at)
        self.assertEqual(lead.ip, "10.1.2.3")
        self.assertEqual(lead.status, "new")

    def test_without_consent_error(self):
        response = self.client.post(URL, valid_data(consent=""))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/lead_form_page.html")
        self.assertIn(MSG_CONSENT_REQUIRED, response.context["form"].errors["consent"])
        self.assertFalse(Lead.objects.exists())

    def test_bad_phone_error(self):
        response = self.client.post(URL, valid_data(phone="123"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("phone", response.context["form"].errors)
        self.assertFalse(Lead.objects.exists())

    def test_honeypot_not_saved(self):
        response = self.client.post(URL, valid_data(website="http://spam.example"))
        self.assertRedirects(response, reverse("core:lead_success"), fetch_redirect_response=False)
        self.assertFalse(Lead.objects.exists())

    def test_rate_limit(self):
        make_org()
        for i in range(5):
            response = self.client.post(URL, valid_data(name=f"Иван {i}"), REMOTE_ADDR="10.0.0.5")
            self.assertEqual(response.status_code, 302)
        response = self.client.post(URL, valid_data(), REMOTE_ADDR="10.0.0.5")
        self.assertEqual(response.status_code, 429)
        self.assertIn("Слишком много заявок", str(response.context["form"].non_field_errors()))
        self.assertIn("+7 (846) 000-00-00", str(response.context["form"].non_field_errors()))
        self.assertEqual(Lead.objects.count(), 5)
        # Другой IP — не ограничен.
        self.assertEqual(self.client.post(URL, valid_data(), REMOTE_ADDR="10.0.0.6").status_code, 302)

    def test_x_forwarded_for_ignored_by_default(self):
        for _ in range(5):
            self.client.post(URL, valid_data(), REMOTE_ADDR="10.0.0.7", HTTP_X_FORWARDED_FOR=f"1.1.1.{_}")
        response = self.client.post(URL, valid_data(), REMOTE_ADDR="10.0.0.7", HTTP_X_FORWARDED_FOR="9.9.9.9")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(Lead.objects.first().ip, "10.0.0.7")

    @override_settings(USE_X_FORWARDED_FOR=True)
    def test_x_forwarded_for_when_enabled(self):
        self.client.post(URL, valid_data(), REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="spoof, 203.0.113.9")
        self.assertEqual(Lead.objects.get().ip, "203.0.113.9")

    def test_get_form_page(self):
        program = make_program(make_category())
        response = self.client.get(URL, {"program": program.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["program"], program.pk)

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(URL, valid_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Lead.objects.exists())
        # С токеном со страницы — проходит.
        client.get(URL)
        token = client.cookies["csrftoken"].value
        response = client.post(URL, valid_data(csrfmiddlewaretoken=token))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Lead.objects.count(), 1)

    async def test_async_client_post(self):
        client = AsyncClient()
        response = await client.post(URL, valid_data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(await Lead.objects.acount(), 1)


@with_stub_templates
@override_settings(
    EMAIL_HOST="smtp.example.com",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    LEADS_EMAIL_TO=["boss@example.com"],
    SITE_URL="https://uc.example.ru",
    TELEGRAM_BOT_TOKEN="",
    TELEGRAM_CHAT_ID="",
)
class NotifyTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_email_without_personal_data(self):
        self.client.post(URL, valid_data())
        lead = Lead.objects.get()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, f"Новая заявка #{lead.pk}")
        self.assertIn(f"https://uc.example.ru/admin/core/lead/{lead.pk}/change/", message.body)
        for secret in ("Иван", "123-45-67", "ivan@example.com", "Ромашка"):
            self.assertNotIn(secret, message.body + message.subject)

    def test_email_error_does_not_break_request(self):
        with mock.patch("core.notify.send_mail", side_effect=OSError("smtp down")):
            with self.assertLogs("core.notify", level=logging.ERROR):
                response = self.client.post(URL, valid_data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Lead.objects.count(), 1)

    @override_settings(TELEGRAM_BOT_TOKEN="123:abc", TELEGRAM_CHAT_ID="42", EMAIL_HOST="")
    def test_telegram_message(self):
        sent = {}

        def handler(request):
            sent["url"] = str(request.url)
            sent["body"] = json.loads(request.content)
            return httpx.Response(200, json={"ok": True})

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await notify.send_telegram(77, client=client)

        self.assertTrue(asyncio.run(run()))
        self.assertIn("/bot123:abc/sendMessage", sent["url"])
        self.assertEqual(sent["body"]["chat_id"], "42")
        self.assertEqual(sent["body"]["text"], "Новая заявка #77\nhttps://uc.example.ru/admin/core/lead/77/change/")

    @override_settings(TELEGRAM_BOT_TOKEN="123:abc", TELEGRAM_CHAT_ID="42", EMAIL_HOST="")
    def test_telegram_error_logged_without_token(self):
        def handler(request):
            raise httpx.ConnectError("boom 123:abc")

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await notify.send_telegram(5, client=client)

        with self.assertLogs("core.notify", level=logging.ERROR) as logs:
            self.assertFalse(asyncio.run(run()))
        self.assertNotIn("123:abc", "\n".join(logs.output))

    @override_settings(NOTIFY_TIMEOUT=0.2, TELEGRAM_BOT_TOKEN="t", TELEGRAM_CHAT_ID="1", EMAIL_HOST="")
    def test_notify_timeout(self):
        async def slow(lead_id, client=None):
            await asyncio.sleep(5)

        with mock.patch("core.notify.send_telegram", slow):
            with self.assertLogs("core.notify", level=logging.WARNING):
                channels = asyncio.run(asyncio.wait_for(notify.notify_new_lead(1), timeout=2))
        self.assertEqual(channels, ["telegram"])


class LeadAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("boss", "boss@example.com", "pass12345")
        cls.lead = Lead.objects.create(
            name="Иван", phone="+79001234567", email="i@example.com", consent=True, ip="10.0.0.1", comment="тест"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_changelist_and_change_pages(self):
        self.assertEqual(self.client.get("/admin/core/lead/").status_code, 200)
        self.assertEqual(self.client.get(f"/admin/core/lead/{self.lead.pk}/change/").status_code, 200)
        self.assertEqual(self.client.get("/admin/core/lead/add/").status_code, 403)

    def test_export_csv(self):
        response = self.client.post(
            "/admin/core/lead/", {"action": "export_csv", "_selected_action": [self.lead.pk]}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        content = response.content.decode("utf-8-sig")
        self.assertIn("Иван", content)
        self.assertIn("+79001234567", content)

    def test_anonymize(self):
        self.client.post("/admin/core/lead/", {"action": "anonymize", "_selected_action": [self.lead.pk]})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.name, "Обезличено")
        self.assertEqual(self.lead.email, "")
        self.assertIsNone(self.lead.ip)
        self.assertNotIn("9001234567", self.lead.phone)

    def test_admin_index_title(self):
        response = self.client.get("/admin/")
        self.assertContains(response, "Панель учебного центра")
