"""
Юридические требования к сайту (152-ФЗ в ред. 2025, безопасность):
CSP и Permissions-Policy, отсутствие inline-скриптов и внешних ресурсов, чекбокс согласия,
фиксация согласия, тексты Политики и Согласия, отсутствие ПДн в логах и уведомлениях,
удаление данных в панели и команда purge_leads.
"""

import io
import json
import logging
import re
from datetime import timedelta
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock

import httpx
from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Lead

from .helpers import make_category, make_org, make_program

PD = {
    "name": "Аграфена Пантелеймоновна",
    "phone": "+7 (917) 555-44-33",
    "email": "agrafena.secret@example.com",
    "organization": "ООО «Секретная Ромашка»",
    "comment": "Уникальный комментарий 9f3a",
}
PD_MARKERS = ["Аграфена", "555-44-33", "9175554433", "agrafena.secret", "Секретная Ромашка", "9f3a"]


def lead_post_data(**extra):
    data = {**PD, "program": "", "consent": "on", "website": ""}
    data.update(extra)
    return data


def parse_csp(header):
    """"a b; c d" → {"a": ["b"], "c": ["d"]}"""
    result = {}
    for part in header.split(";"):
        tokens = part.split()
        if tokens:
            result[tokens[0]] = tokens[1:]
    return result


def public_urls(program_slug):
    from sveden.models import SECTIONS

    urls = ["/", "/obuchenie/", f"/obuchenie/{program_slug}/", "/kontakty/", "/politika/", "/soglasie/",
            "/zayavka/", "/zayavka/spasibo/", "/sveden/"]
    return urls + [f"/sveden/{slug}/" for slug, _ in SECTIONS]


class ResourceCollector(HTMLParser):
    """Собирает из HTML всё, что влияет на CSP и на передачу данных третьим лицам."""

    def __init__(self):
        super().__init__()
        self.scripts = []  # (attrs, inline_text)
        self.inline_styles = []
        self.style_tags = 0
        self.handlers = []
        self.urls = []  # (tag, attr, value)
        self.iframes = []
        self.checkboxes = []
        self._script = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for name, _ in attrs:
            if name.startswith("on"):
                self.handlers.append((tag, name))
        if "style" in a:
            self.inline_styles.append(tag)
        if tag == "style":
            self.style_tags += 1
        if tag == "script":
            self._script = [a, ""]
        if tag == "iframe":
            self.iframes.append(a.get("src", ""))
        if tag == "input" and a.get("type") == "checkbox":
            self.checkboxes.append(a)
        for attr in ("src", "srcset"):
            if a.get(attr):
                self.urls.append((tag, attr, a[attr]))
        # canonical/alternate — просто ссылки; загружаются только stylesheet, icon, preload и т.п.
        rel = (a.get("rel") or "").lower().split()
        if tag == "link" and a.get("href") and set(rel) & {"stylesheet", "icon", "preload", "modulepreload",
                                                           "manifest", "apple-touch-icon", "prefetch"}:
            self.urls.append((tag, " ".join(rel), a["href"]))

    def handle_data(self, data):
        if self._script is not None:
            self._script[1] += data

    def handle_endtag(self, tag):
        if tag == "script" and self._script is not None:
            self.scripts.append(tuple(self._script))
            self._script = None


def collect(html):
    parser = ResourceCollector()
    parser.feed(html)
    return parser


def is_local(url):
    return not re.match(r"^(https?:)?//", url.strip(), re.IGNORECASE)


# --- 1. CSP и Permissions-Policy ---------------------------------------------

class SecurityHeadersTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_org()

    def test_site_csp_is_strict(self):
        response = self.client.get("/")
        csp = parse_csp(response["Content-Security-Policy"])
        self.assertEqual(csp["default-src"], ["'self'"])
        self.assertEqual(csp["script-src"], ["'self'"])
        self.assertEqual(csp["style-src"], ["'self'"])
        self.assertEqual(csp["img-src"], ["'self'", "data:"])
        self.assertEqual(csp["font-src"], ["'self'"])
        self.assertEqual(csp["frame-src"], ["https://yandex.ru", "https://*.yandex.ru"])
        self.assertEqual(csp["form-action"], ["'self'"])
        self.assertEqual(csp["frame-ancestors"], ["'none'"])
        self.assertEqual(csp["base-uri"], ["'self'"])
        self.assertEqual(csp["object-src"], ["'none'"])
        header = response["Content-Security-Policy"]
        self.assertNotIn("unsafe-inline", header)
        self.assertNotIn("unsafe-eval", header)

    def test_csp_on_all_public_pages_and_errors(self):
        program = make_program(make_category())
        for url in public_urls(program.slug) + ["/net-takoi-stranicy/"]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn("Content-Security-Policy", response)
                self.assertIn("Permissions-Policy", response)

    def test_admin_csp_allows_only_inline_styles(self):
        response = self.client.get("/admin/login/")
        csp = parse_csp(response["Content-Security-Policy"])
        self.assertEqual(csp["style-src"], ["'self'", "'unsafe-inline'"])
        self.assertEqual(csp["script-src"], ["'self'"])
        self.assertEqual(csp["frame-ancestors"], ["'none'"])

    def test_permissions_policy(self):
        policy = self.client.get("/")["Permissions-Policy"]
        for feature in ("camera=()", "microphone=()", "geolocation=()", "payment=()", "usb=()"):
            self.assertIn(feature, policy)

    @override_settings(CSP_REPORT_ONLY=True)
    def test_report_only_mode(self):
        response = self.client.get("/")
        self.assertIn("Content-Security-Policy-Report-Only", response)
        self.assertNotIn("Content-Security-Policy", response)


# --- 2. Нет inline-скриптов/стилей и внешних ресурсов (шрифты, CDN) ------------

class NoInlineCodeNoExternalResourcesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_org(map_embed_url="https://yandex.ru/map-widget/v1/?um=constructor%3Atest&source=constructor")
        cls.program = make_program(make_category())

    def setUp(self):
        cache.clear()

    def test_rendered_pages_are_csp_clean(self):
        for url in public_urls(self.program.slug):
            with self.subTest(url=url):
                page = collect(self.client.get(url).content.decode())
                for attrs, text in page.scripts:
                    if attrs.get("src"):
                        self.assertTrue(attrs["src"].startswith("/static/"), f"внешний скрипт {attrs['src']}")
                    else:
                        # Без src допускаются только блоки данных (JSON-LD): браузер их не исполняет.
                        self.assertEqual(attrs.get("type"), "application/ld+json", f"inline-скрипт: {text[:80]}")
                self.assertEqual(page.inline_styles, [], "style=… заблокирует CSP style-src 'self'")
                self.assertEqual(page.style_tags, 0, "<style> заблокирует CSP style-src 'self'")
                self.assertEqual(page.handlers, [], "onclick=… и т.п. заблокирует CSP")
                for tag, attr, value in page.urls:
                    if tag == "iframe":
                        continue
                    self.assertTrue(is_local(value) or value.startswith("data:"), f"{tag} {attr}={value}")

    def test_map_iframe_only_from_yandex(self):
        page = collect(self.client.get("/kontakty/").content.decode())
        self.assertTrue(page.iframes, "на «Контактах» должна быть карта при заданном map_embed_url")
        for src in page.iframes:
            self.assertRegex(src, r"^https://([a-z0-9-]+\.)*yandex\.ru/")

    def test_css_has_no_external_imports_and_fonts_are_local(self):
        css_dir = Path(settings.BASE_DIR) / "static" / "css"
        for css in css_dir.glob("*.css"):
            text = css.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"@import\s+(url\()?['\"]?(https?:)?//", css.name)
            for url in re.findall(r"url\(\s*['\"]?([^'\")]+)", text):
                self.assertTrue(is_local(url), f"{css.name}: {url}")
        self.assertTrue(list((Path(settings.BASE_DIR) / "static" / "fonts").glob("*.woff2")))


# --- 3. Чекбокс согласия и фиксация согласия -----------------------------------

class ConsentCheckboxTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_org()

    def setUp(self):
        cache.clear()

    def test_checkbox_unchecked_with_two_links(self):
        for url in ("/", "/zayavka/", "/kontakty/"):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                boxes = [b for b in collect(html).checkboxes if b.get("name") == "consent"]
                if url == "/zayavka/":
                    self.assertTrue(boxes, "на странице заявки должен быть чекбокс согласия")
                for box in boxes:
                    self.assertNotIn("checked", box, "чекбокс согласия не должен быть отмечен заранее")
                    self.assertIn("required", box)
                if boxes:
                    self.assertIn('href="/soglasie/"', html)
                    self.assertIn('href="/politika/"', html)

    def test_lead_without_consent_rejected(self):
        response = self.client.post("/zayavka/", lead_post_data(consent=""))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Lead.objects.count(), 0)

    def test_consent_version_time_and_ip_saved(self):
        before = timezone.now()
        response = self.client.post("/zayavka/", lead_post_data(), REMOTE_ADDR="203.0.113.7")
        self.assertRedirects(response, "/zayavka/spasibo/", fetch_redirect_response=False)
        lead = Lead.objects.get()
        self.assertTrue(lead.consent)
        self.assertEqual(lead.consent_version, settings.CONSENT_VERSION)
        self.assertTrue(before <= lead.consent_at <= timezone.now())
        self.assertEqual(lead.ip, "203.0.113.7")


# --- 4. Тексты Политики и Согласия ---------------------------------------------

class LegalTextsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_org()

    def text(self, url):
        html = self.client.get(url).content.decode()
        return " ".join(re.sub(r"<[^>]+>", " ", html).split())

    def test_consent_is_separate_document_with_required_parts(self):
        consent = self.text("/soglasie/")
        for part in (
            settings.CONSENT_VERSION,          # версия согласия
            "Автономная некоммерческая организация ДПО «Тест»",  # оператор
            "6300000000",                      # ИНН
            "г. Самара, ул. Тестовая, 1",      # адрес
            "Цель обработки",
            "Перечень персональных данных",
            "IP-адрес",
            "Сбор, запись",                    # действия
            "смешанная",                       # способ обработки
            "1 год",                           # срок
            "30 дней",
            "отозвать согласие",
            "трансграничная передача не осуществляются",
            "территории Российской Федерации",
        ):
            self.assertIn(part, consent)
        # Согласие — отдельная страница, не часть Политики (152-ФЗ в ред. 156-ФЗ, с 01.09.2025).
        self.assertNotIn("Настоящая Политика", consent)
        self.assertNotIn("своей волей и в своём интересе", self.text("/politika/"))

    def test_policy_required_parts_and_customer_todo(self):
        html = self.client.get("/politika/").content.decode()
        policy = self.text("/politika/")
        for part in (
            "6300000000",
            "ч. 2 ст. 18.1",
            "1 год с даты получения заявки",
            "30 дней",
            "Трансграничная передача персональных данных не осуществляется",
            "территории Российской Федерации",
            "отозвать согласие",
            "Роскомнадзор",
            "csrftoken",
            "Яндекс Карты",
        ):
            self.assertIn(part, policy)
        self.assertIn("[ЗАКАЗЧИК:", html)

    def test_retention_matches_settings(self):
        # «1 год» в текстах ↔ LEAD_RETENTION_DAYS, который использует purge_leads.
        self.assertEqual(settings.LEAD_RETENTION_DAYS, 365)
        self.assertIn("1 год", self.text("/soglasie/"))
        self.assertIn("1 год", self.text("/politika/"))


# --- 5. ПДн не уходят в логи, Telegram и e-mail -------------------------------

@override_settings(
    SITE_URL="https://uc.example.ru",
    EMAIL_HOST="smtp.example.ru",
    LEADS_EMAIL_TO=["boss@example.ru"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    TELEGRAM_BOT_TOKEN="123:secret-token",
    TELEGRAM_CHAT_ID="42",
)
class NoPersonalDataLeakTests(TestCase):
    def setUp(self):
        cache.clear()
        self.telegram = []

        def handler(request):
            self.telegram.append(json.loads(request.content))
            return httpx.Response(200, json={"ok": True})

        real_client = httpx.AsyncClient

        def fake_client(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            return real_client(*args, **kwargs)

        patcher = mock.patch("core.notify.httpx.AsyncClient", side_effect=fake_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def assert_no_pd(self, text, where):
        for marker in PD_MARKERS:
            self.assertNotIn(marker, text, f"ПДн «{marker}» попали в {where}")

    def test_notifications_and_logs_without_pd(self):
        with self.assertLogs("core", level=logging.DEBUG) as logs:
            response = self.client.post("/zayavka/", lead_post_data())
        self.assertEqual(response.status_code, 302)
        lead = Lead.objects.get()

        self.assertEqual(len(self.telegram), 1)
        self.assertEqual(self.telegram[0]["text"], f"Новая заявка #{lead.pk}\nhttps://uc.example.ru/admin/core/lead/{lead.pk}/change/")
        self.assert_no_pd(json.dumps(self.telegram, ensure_ascii=False), "Telegram")

        self.assertEqual(len(mail.outbox), 1)
        self.assert_no_pd(mail.outbox[0].subject + mail.outbox[0].body, "e-mail")

        self.assert_no_pd("\n".join(logs.output), "лог")

    def test_invalid_form_does_not_log_pd(self):
        with self.assertLogs("core", level=logging.DEBUG) as logs:
            logging.getLogger("core").debug("маркер")  # assertLogs требует хотя бы одну запись
            self.client.post("/zayavka/", lead_post_data(phone="12"))
            self.client.post("/zayavka/", lead_post_data(website="http://spam"))
        self.assertEqual(Lead.objects.count(), 0)
        self.assert_no_pd("\n".join(logs.output), "лог")

    def test_notify_failure_logs_without_pd_and_token(self):
        with mock.patch("core.notify.send_mail", side_effect=OSError(f"smtp {PD['email']}")):
            with self.assertLogs("core", level=logging.DEBUG) as logs:
                self.client.post("/zayavka/", lead_post_data())
        output = "\n".join(logs.output)
        self.assert_no_pd(output, "лог")
        self.assertNotIn("secret-token", output)


# --- 6. Удаление данных в панели -------------------------------------------------

class AdminDeletionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("boss", "boss@example.com", "pass12345")

    def setUp(self):
        self.client.force_login(self.admin)
        self.lead = Lead.objects.create(consent=True, ip="10.0.0.1", **PD)

    def test_actions_available(self):
        html = self.client.get("/admin/core/lead/").content.decode()
        self.assertIn('value="delete_selected"', html)
        self.assertIn('value="anonymize"', html)

    def test_delete_selected_removes_lead(self):
        self.client.post(
            "/admin/core/lead/",
            {"action": "delete_selected", "_selected_action": [self.lead.pk], "post": "yes"},
        )
        self.assertFalse(Lead.objects.filter(pk=self.lead.pk).exists())

    def test_anonymize_clears_all_pd(self):
        self.client.post("/admin/core/lead/", {"action": "anonymize", "_selected_action": [self.lead.pk]})
        self.lead.refresh_from_db()
        values = " ".join(str(getattr(self.lead, f)) for f in ("name", "phone", "email", "organization", "comment"))
        for marker in PD_MARKERS:
            self.assertNotIn(marker, values)
        self.assertIsNone(self.lead.ip)


# --- 7. Команда purge_leads ------------------------------------------------------

class PurgeLeadsTests(TestCase):
    def make_lead(self, days_ago, status="new", **extra):
        lead = Lead.objects.create(consent=True, ip="10.0.0.1", status=status, **{**PD, **extra})
        Lead.objects.filter(pk=lead.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
        return lead

    def run_cmd(self, *args):
        out = io.StringIO()
        call_command("purge_leads", *args, stdout=out)
        return out.getvalue()

    def test_default_retention(self):
        old = self.make_lead(400)
        fresh = self.make_lead(10)
        old_spam = self.make_lead(40, status="spam")
        fresh_spam = self.make_lead(5, status="spam")
        output = self.run_cmd()
        remaining = set(Lead.objects.values_list("pk", flat=True))
        self.assertEqual(remaining, {fresh.pk, fresh_spam.pk})
        self.assertIn(f"#{old.pk}", output)
        self.assertIn(f"#{old_spam.pk}", output)
        self.assertIn("Удалено заявок: 2", output)

    def test_dry_run_changes_nothing(self):
        old = self.make_lead(400)
        output = self.run_cmd("--dry-run")
        self.assertTrue(Lead.objects.filter(pk=old.pk).exists())
        self.assertIn(f"#{old.pk}", output)
        self.assertIn("ничего не изменено", output)

    def test_custom_days(self):
        self.make_lead(10)
        self.make_lead(2)
        self.run_cmd("--days", "5")
        self.assertEqual(Lead.objects.count(), 1)

    def test_invalid_days(self):
        with self.assertRaises(CommandError):
            call_command("purge_leads", "--days", "0", stdout=io.StringIO())

    def test_anonymize_mode(self):
        old = self.make_lead(400)
        self.run_cmd("--anonymize")
        old.refresh_from_db()
        self.assertEqual(old.name, "Обезличено")
        self.assertIsNone(old.ip)
        self.assertEqual(old.email, "")
        # Повторный запуск не трогает уже обезличенные.
        self.assertIn("обезличивания: 0", self.run_cmd("--anonymize"))

    def test_output_and_admin_log_without_pd(self):
        old = self.make_lead(400)
        user = get_user_model().objects.create_superuser("boss", "boss@example.com", "pass12345")
        LogEntry.objects.create(
            user=user,
            content_type=ContentType.objects.get_for_model(Lead),
            object_id=str(old.pk),
            object_repr=f"Заявка #{old.pk} от {PD['name']}",
            action_flag=CHANGE,
            change_message="[]",
        )
        output = self.run_cmd()
        for marker in PD_MARKERS:
            self.assertNotIn(marker, output)
        self.assertEqual(LogEntry.objects.get().object_repr, f"Заявка #{old.pk}")

    def test_nothing_to_delete(self):
        self.make_lead(1)
        self.assertIn("Заявок для удаления: 0", self.run_cmd())
        self.assertEqual(Lead.objects.count(), 1)
