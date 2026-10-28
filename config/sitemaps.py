"""
Карта сайта /sitemap.xml: все публичные страницы + опубликованные программы.

Домен берётся из SITE_URL (если задан), иначе — из адреса текущего запроса.
"""

from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from core.models import Program
from sveden.models import SECTIONS, Organization


class SiteUrlMixin:
    """Подставляет домен и протокол из settings.SITE_URL."""

    def get_domain(self, site=None):
        if settings.SITE_URL:
            return urlsplit(settings.SITE_URL).netloc
        return super().get_domain(site)

    def get_protocol(self, protocol=None):
        if settings.SITE_URL:
            return urlsplit(settings.SITE_URL).scheme or "https"
        return super().get_protocol(protocol)


class StaticPagesSitemap(SiteUrlMixin, Sitemap):
    """Постоянные страницы сайта."""

    changefreq = "weekly"

    def items(self):
        return [
            ("core:home", 1.0),
            ("core:program_list", 0.9),
            ("core:contacts", 0.7),
            ("core:privacy", 0.2),
            ("core:consent", 0.2),
        ]

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]


class SvedenSitemap(SiteUrlMixin, Sitemap):
    """Раздел «Сведения об образовательной организации» и все его подразделы."""

    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return ["index"] + [slug for slug, _title in SECTIONS]

    def location(self, item):
        return reverse(f"sveden:{item}")

    def lastmod(self, item):
        org = Organization.load()
        return org.updated_at if org else None


class ProgramSitemap(SiteUrlMixin, Sitemap):
    """Страницы опубликованных программ."""

    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return Program.objects.filter(is_published=True).order_by("order", "title")

    def lastmod(self, obj):
        return obj.updated_at


sitemaps = {
    "pages": StaticPagesSitemap,
    "sveden": SvedenSitemap,
    "programs": ProgramSitemap,
}
