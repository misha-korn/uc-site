"""
Главная таблица адресов проекта.

/            — публичная часть (core/urls.py)
/sveden/     — раздел «Сведения об образовательной организации» (sveden/urls.py)
/admin/      — панель заказчика
/sitemap.xml, /robots.txt — для поисковиков
/media/...   — загруженные файлы: Django отдаёт их сам только при DEBUG=1 или SITE_DEMO=1
               (settings.SERVE_MEDIA); на боевом сервере их раздаёт nginx.
"""

import re

from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path
from django.views.static import serve

from core.views import robots_txt

from .sitemaps import sitemaps

# Заголовки панели управления (вместо «Администрирование Django»).
admin.site.site_header = "Панель учебного центра"
admin.site.site_title = "Панель учебного центра"
admin.site.index_title = "Управление сайтом"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path("robots.txt", robots_txt, name="robots"),
    path("sveden/", include("sveden.urls")),
    path("", include("core.urls")),
]

if settings.SERVE_MEDIA:
    # django.conf.urls.static.static() работает только при DEBUG=True,
    # поэтому для демо-режима подключаем serve напрямую.
    urlpatterns += [
        re_path(
            r"^%s(?P<path>.*)$" % re.escape(settings.MEDIA_URL.lstrip("/")),
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
