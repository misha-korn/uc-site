"""
Заголовки Content-Security-Policy и Permissions-Policy.

Зачем: CSP запрещает браузеру выполнять любые скрипты, кроме наших файлов из /static/
(никаких inline-скриптов, CDN и чужих счётчиков). Если злоумышленник сумеет вставить на
страницу <script> (XSS), браузер его не выполнит — персональные данные из формы не утекут.

Политики задаются в settings.py (CSP_DIRECTIVES, CSP_ADMIN_DIRECTIVES, PERMISSIONS_POLICY).
Подключить Яндекс Метрику и т. п. — только добавив её домены в CSP_DIRECTIVES и в Политику ПДн.
Отладка: CSP_REPORT_ONLY=1 — браузер не блокирует, а только пишет нарушения в консоль.

Работает и в sync-, и в async-режиме (MiddlewareMixin сам выбирает режим).
"""

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


def build_policy(directives):
    """{'default-src': ["'self'"], ...} → "default-src 'self'; ..." (пустой список → директива без значений)."""
    parts = []
    for name, sources in directives.items():
        parts.append(" ".join([name, *sources]) if sources else name)
    return "; ".join(parts)


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Добавляет CSP и Permissions-Policy к HTML-ответам, если view не задал их сам."""

    def __init__(self, get_response):
        super().__init__(get_response)
        self.site_policy = build_policy(settings.CSP_DIRECTIVES)
        self.admin_policy = build_policy(settings.CSP_ADMIN_DIRECTIVES)
        self.admin_prefix = getattr(settings, "CSP_ADMIN_PREFIX", "/admin/")
        self.header = (
            "Content-Security-Policy-Report-Only" if settings.CSP_REPORT_ONLY else "Content-Security-Policy"
        )

    def process_response(self, request, response):
        # Отладочные страницы Django (DEBUG=1, ошибки 404/500) построены на inline-стилях и скриптах —
        # строгая CSP сделала бы их нечитаемыми. В бою (DEBUG=0) CSP ставится на все ответы.
        if settings.DEBUG and response.status_code >= 400:
            return response
        if "Content-Security-Policy" not in response and "Content-Security-Policy-Report-Only" not in response:
            is_admin = request.path.startswith(self.admin_prefix)
            response[self.header] = self.admin_policy if is_admin else self.site_policy
        if settings.PERMISSIONS_POLICY and "Permissions-Policy" not in response:
            response["Permissions-Policy"] = settings.PERMISSIONS_POLICY
        return response
