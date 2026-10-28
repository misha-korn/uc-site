"""
Автоудаление заявок по истечении срока хранения (152-ФЗ, ч. 4–5 ст. 21).

Срок — из Политики и Согласия: «1 год с даты заявки» → settings.LEAD_RETENTION_DAYS (365).
Заявки со статусом «Спам» — через settings.LEAD_SPAM_RETENTION_DAYS (30) дней.
Запускать раз в сутки (cron или systemd-таймер, см. DEPLOY.md) — тогда данные уничтожаются
не позже чем через сутки после окончания срока (закон даёт 30 дней).

Примеры:
    python manage.py purge_leads --dry-run        # только показать, что будет удалено
    python manage.py purge_leads                  # удалить заявки старше 365 дней (спам — старше 30)
    python manage.py purge_leads --days 180       # свой срок
    python manage.py purge_leads --anonymize      # не удалять строки, а стереть ПДн (статистика сохранится)

Вывод команды не содержит персональных данных — только номера и даты заявок. Его можно
сохранять как «выгрузку из журнала» для акта об уничтожении ПДн (приказ Роскомнадзора № 179).
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import Lead

logger = logging.getLogger("core.purge_leads")

# Те же значения, что у действия «Удалить персональные данные (обезличить)» в панели.
ANONYMIZED_VALUES = {
    "name": "Обезличено",
    "phone": "—",
    "email": "",
    "organization": "",
    "comment": "",
    "staff_note": "",
    "ip": None,
}


def positive_int(value):
    number = int(value)
    if number < 1:
        raise ValueError("нужно целое число ≥ 1")
    return number


class Command(BaseCommand):
    help = "Удаляет (или обезличивает) заявки старше срока хранения из Политики обработки ПДн."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=positive_int,
            default=None,
            help=f"Срок хранения в днях (по умолчанию LEAD_RETENTION_DAYS = {settings.LEAD_RETENTION_DAYS}).",
        )
        parser.add_argument(
            "--spam-days",
            type=positive_int,
            default=None,
            help=f"Срок для заявок со статусом «Спам» (по умолчанию {settings.LEAD_SPAM_RETENTION_DAYS}).",
        )
        parser.add_argument("--dry-run", action="store_true", help="Ничего не менять, только показать.")
        parser.add_argument(
            "--anonymize",
            action="store_true",
            help="Не удалять заявки, а стереть в них персональные данные (дата, программа, статус останутся).",
        )

    def handle(self, *args, days=None, spam_days=None, dry_run=False, anonymize=False, **options):
        days = days or settings.LEAD_RETENTION_DAYS
        spam_days = spam_days or settings.LEAD_SPAM_RETENTION_DAYS
        if days < 1 or spam_days < 1:
            raise CommandError("Срок хранения должен быть не меньше 1 дня.")

        now = timezone.now()
        expired = Q(created_at__lt=now - timedelta(days=days))
        spam_expired = Q(status="spam", created_at__lt=now - timedelta(days=min(spam_days, days)))
        queryset = Lead.objects.filter(expired | spam_expired)
        if anonymize:
            # Уже обезличенные повторно не трогаем.
            queryset = queryset.exclude(name=ANONYMIZED_VALUES["name"], ip__isnull=True, email="", comment="")

        rows = list(queryset.order_by("created_at").values_list("pk", "created_at"))
        ids = [pk for pk, _ in rows]
        action = "обезличивания" if anonymize else "удаления"
        self.stdout.write(
            f"Срок хранения: {days} дн. (спам — {min(spam_days, days)} дн.). Заявок для {action}: {len(ids)}."
        )
        for pk, created in rows:
            self.stdout.write(f"  #{pk} от {timezone.localtime(created):%d.%m.%Y}")

        if dry_run or not ids:
            if dry_run:
                self.stdout.write("Режим --dry-run: ничего не изменено.")
            return

        with transaction.atomic():
            if anonymize:
                done = Lead.objects.filter(pk__in=ids).update(**ANONYMIZED_VALUES)
            else:
                done, _ = Lead.objects.filter(pk__in=ids).delete()
            scrubbed = self.scrub_admin_log(ids)

        verb = "Обезличено" if anonymize else "Удалено"
        self.stdout.write(self.style.SUCCESS(f"{verb} заявок: {done}. Очищено записей журнала панели: {scrubbed}."))
        logger.info("purge_leads: %s заявок: %s (№ %s)", verb.lower(), done, ", ".join(map(str, ids)))

    @staticmethod
    def scrub_admin_log(ids):
        """Журнал действий панели (django_admin_log) хранит название объекта — там может быть имя
        из заявки. Заменяем его на безличное «Заявка #N»."""
        content_type = ContentType.objects.get_for_model(Lead)
        entries = LogEntry.objects.filter(content_type=content_type, object_id__in=[str(pk) for pk in ids])
        count = 0
        for entry in entries.only("pk", "object_id"):
            LogEntry.objects.filter(pk=entry.pk).update(object_repr=f"Заявка #{entry.object_id}")
            count += 1
        return count
