from django.apps import AppConfig


class SvedenConfig(AppConfig):
    """Раздел «Сведения об образовательной организации» (Приказ Рособрнадзора № 1493)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "sveden"
    verbose_name = "Сведения об образовательной организации"
