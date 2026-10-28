"""Тесты для деплоя на PaaS: гостевой вход в панель на демо-стенде."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings


class DemoViewerTests(TestCase):
    """Пользователь demo создаётся только на демо-стенде и может только смотреть."""

    @override_settings(SITE_DEMO=True)
    def test_viewer_is_read_only_and_without_leads(self):
        with mock.patch.dict("os.environ", {"DEMO_VIEWER_PASSWORD": "Pokaz-2026-uc"}):
            call_command("seed_demo", "--no-pdf", verbosity=0)
        user = get_user_model().objects.get(username="demo")
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("Pokaz-2026-uc"))
        self.assertTrue(user.has_perm("core.view_program"))
        self.assertTrue(user.has_perm("sveden.view_document"))
        self.assertFalse(user.has_perm("core.change_program"))
        self.assertFalse(user.has_perm("sveden.delete_document"))
        self.assertFalse(user.has_perm("core.view_lead"))

    @override_settings(SITE_DEMO=False)
    def test_viewer_not_created_on_production(self):
        with mock.patch.dict("os.environ", {"DEMO_VIEWER_PASSWORD": "Pokaz-2026-uc"}):
            call_command("seed_demo", "--no-pdf", verbosity=0)
        self.assertFalse(get_user_model().objects.filter(username="demo").exists())
