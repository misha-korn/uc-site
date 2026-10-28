"""Тесты страниц: все URL отвечают 200, контекст по контракту, 404, sitemap, robots."""

from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.core.cache import cache
from django.test import AsyncClient, TestCase, override_settings
from django.urls import reverse

from core.forms import LeadForm
from sveden.models import SECTIONS

from .helpers import make_category, make_org, make_program, with_stub_templates

PUBLIC_URL_NAMES = [
    "core:home",
    "core:program_list",
    "core:contacts",
    "core:lead_create",
    "core:lead_success",
    "core:privacy",
    "core:consent",
    "sveden:index",
] + [f"sveden:{slug}" for slug, _ in SECTIONS]


def all_public_urls(program_slug=None):
    urls = [reverse(name) for name in PUBLIC_URL_NAMES]
    if program_slug:
        urls.append(reverse("core:program_detail", args=[program_slug]))
    return urls + ["/robots.txt", "/sitemap.xml"]


@with_stub_templates
class EmptyDatabasePagesTests(TestCase):
    """Сайт не должен падать, пока заказчик ничего не заполнил."""

    def test_all_pages_200_without_data(self):
        for url in all_public_urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, url)

    def test_context_processor_without_org(self):
        response = self.client.get(reverse("core:home"))
        self.assertIsNone(response.context["org"])
        self.assertEqual(response.context["nav_categories"], [])
        self.assertEqual(len(response.context["sveden_sections"]), 14)
        self.assertIsInstance(response.context["lead_form"], LeadForm)
        self.assertEqual(response.context["consent_version"], settings.CONSENT_VERSION)
        self.assertIn("site_demo", response.context)


@with_stub_templates
class PagesWithDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.cat = make_category()
        cls.other_cat = make_category(slug="pozharnaya", name="Пожарная безопасность", order=2)
        cls.program = make_program(cls.cat, slug="ot-a")
        cls.p2 = make_program(cls.cat, slug="ot-b", is_popular=False)
        cls.p3 = make_program(cls.other_cat, slug="ptm")
        cls.hidden = make_program(cls.cat, slug="hidden", is_published=False)

    def test_all_pages_200_with_data(self):
        for url in all_public_urls(self.program.slug):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_templates_used(self):
        cases = {
            reverse("core:home"): "core/home.html",
            reverse("core:program_list"): "core/program_list.html",
            reverse("core:program_detail", args=["ot-a"]): "core/program_detail.html",
            reverse("core:contacts"): "core/contacts.html",
            reverse("core:lead_success"): "core/lead_success.html",
            reverse("core:privacy"): "core/privacy.html",
            reverse("core:consent"): "core/consent.html",
            reverse("sveden:index"): "sveden/index.html",
        }
        for slug, _ in SECTIONS:
            cases[reverse(f"sveden:{slug}")] = f"sveden/{slug}.html"
        for url, template in cases.items():
            with self.subTest(url=url):
                self.assertTemplateUsed(self.client.get(url), template)

    def test_home_context(self):
        ctx = self.client.get(reverse("core:home")).context
        self.assertIsInstance(ctx["popular_programs"], list)
        self.assertEqual({p.slug for p in ctx["popular_programs"]}, {"ot-a", "ptm"})  # без скрытой
        cats = {c.slug: c for c in ctx["categories"]}
        self.assertEqual(cats["ohrana-truda"].programs_count, 2)
        for key in ("advantages", "faq", "steps", "stats"):
            self.assertIsInstance(ctx[key], list)
        self.assertEqual(ctx["org"], self.org)

    def test_program_list_filter(self):
        ctx = self.client.get(reverse("core:program_list"), {"cat": "pozharnaya"}).context
        self.assertEqual(ctx["active_category"], self.other_cat)
        self.assertEqual([p.slug for p in ctx["programs"]], ["ptm"])
        ctx = self.client.get(reverse("core:program_list"), {"cat": "net-takoi"}).context
        self.assertIsNone(ctx["active_category"])
        self.assertEqual(len(ctx["programs"]), 3)
        self.assertIsInstance(ctx["programs"], list)

    def test_program_detail_context_and_404(self):
        response = self.client.get(self.program.get_absolute_url())
        self.assertEqual(response.context["program"], self.program)
        self.assertEqual([p.slug for p in response.context["related"]], ["ot-b"])
        self.assertEqual(response.context["lead_form"].initial["program"], self.program.pk)
        self.assertEqual(self.client.get("/obuchenie/hidden/").status_code, 404)
        self.assertEqual(self.client.get("/obuchenie/net-takoi/").status_code, 404)

    def test_program_properties(self):
        self.assertEqual(self.program.disciplines_list, ["Модуль 1", "Модуль 2"])
        self.assertEqual(self.program.level_display, "Дополнительное профессиональное образование")
        self.program.kind = "po"
        self.assertEqual(self.program.level_display, "Профессиональное обучение")
        self.assertEqual(self.program.get_absolute_url(), "/obuchenie/ot-a/")

    def test_post_to_get_only_page_not_allowed(self):
        self.assertEqual(self.client.post(reverse("core:home")).status_code, 405)


class SeoFilesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = make_category()
        make_program(cat, slug="ot-a")
        make_program(cat, slug="hidden", is_published=False)

    @override_settings(SITE_DEMO=False)
    def test_robots(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        text = response.content.decode()
        self.assertIn("Disallow: /admin/", text)
        self.assertIn("Sitemap: ", text)
        self.assertNotIn("Disallow: /\n", text)

    @override_settings(SITE_DEMO=True)
    def test_robots_demo_forbids_indexing(self):
        self.assertIn("Disallow: /\n", self.client.get("/robots.txt").content.decode())

    @override_settings(SITE_URL="https://uc.example.ru")
    def test_sitemap(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        xml = response.content.decode()
        self.assertIn("<loc>https://uc.example.ru/</loc>", xml)
        self.assertIn("https://uc.example.ru/obuchenie/ot-a/", xml)
        self.assertNotIn("hidden", xml)
        self.assertIn("https://uc.example.ru/sveden/common/", xml)
        self.assertIn("https://uc.example.ru/sveden/eduStandarts/", xml)
        self.assertIn("https://uc.example.ru/kontakty/", xml)
        self.assertNotIn("/admin/", xml)
        self.assertNotIn("/zayavka/", xml)


@with_stub_templates
class AsyncClientTests(TestCase):
    """Проверка через AsyncClient — так запросы обрабатываются под uvicorn."""

    async def test_async_pages(self):
        client = AsyncClient()
        for url in ("/", "/obuchenie/", "/sveden/", "/sveden/employees/"):
            with self.subTest(url=url):
                response = await client.get(url)
                self.assertEqual(response.status_code, 200)


@with_stub_templates
class SecurityHeadersTests(TestCase):
    def test_headers(self):
        response = self.client.get("/")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Referrer-Policy"], "strict-origin-when-cross-origin")


class MediaServingTests(TestCase):
    @skipUnless(settings.SERVE_MEDIA, "media отдаёт nginx (DEBUG=0 и SITE_DEMO=0)")
    def test_media_route_when_serve_media(self):
        """При DEBUG=1 или SITE_DEMO=1 файлы /media/ отдаёт Django."""
        from django.urls import resolve

        self.assertEqual(resolve("/media/docs/x.pdf").func.__name__, "serve")
        self.assertEqual(self.client.get("/media/docs/net-takogo.pdf").status_code, 404)


HAS_REAL_TEMPLATES = (Path(settings.BASE_DIR) / "templates" / "core" / "home.html").is_file()


@skipUnless(HAS_REAL_TEMPLATES, "Шаблоны frontend ещё не созданы")
class RealTemplatesSmokeTests(TestCase):
    """Когда frontend-шаблоны готовы — каждая страница реально рендерится (и пустая, и с данными)."""

    def setUp(self):
        cache.clear()

    def test_real_render_without_data(self):
        for url in all_public_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_real_render_with_data(self):
        make_org()
        program = make_program(make_category())
        for url in all_public_urls(program.slug):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get("/obuchenie/net-takoi/").status_code, 404)

    def test_real_lead_form_errors_render(self):
        response = self.client.post(reverse("core:lead_create"), {"name": "", "phone": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/lead_form_page.html")

