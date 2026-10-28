"""
Уведомления о новой заявке: e-mail и Telegram.

ВАЖНО (152-ФЗ): в уведомление НЕ попадают персональные данные — только номер
заявки и ссылка в админку. Посмотреть имя и телефон можно, только войдя в панель.

Ошибки отправки записываются в лог и НЕ роняют запрос посетителя. Общее время
ожидания ограничено settings.NOTIFY_TIMEOUT (по умолчанию 5 секунд).
"""

import asyncio
import logging

import httpx
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


def lead_admin_url(lead_id):
    """Полная ссылка на заявку в админке (SITE_URL + путь)."""
    path = reverse("admin:core_lead_change", args=[lead_id])
    return f"{settings.SITE_URL}{path}"


def build_message(lead_id):
    """Текст уведомления — без имени, телефона и прочих ПДн."""
    return f"Новая заявка #{lead_id}\n{lead_admin_url(lead_id)}"


def email_recipients():
    return list(settings.LEADS_EMAIL_TO) or ([settings.EMAIL_HOST_USER] if settings.EMAIL_HOST_USER else [])


async def send_email(lead_id):
    """Письмо на LEADS_EMAIL_TO. send_mail синхронный — запускаем в отдельном потоке."""
    try:
        await sync_to_async(send_mail, thread_sensitive=False)(
            subject=f"Новая заявка #{lead_id}",
            message=build_message(lead_id),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=email_recipients(),
            fail_silently=False,
        )
        logger.info("Уведомление о заявке #%s отправлено на e-mail", lead_id)
        return True
    except Exception as exc:  # noqa: BLE001 — любая ошибка почты не должна ронять сайт
        logger.error("Не удалось отправить e-mail о заявке #%s: %s", lead_id, exc.__class__.__name__)
        return False


async def send_telegram(lead_id, client=None):
    """Сообщение в Telegram через Bot API. Токен в лог не пишем."""
    url = f"{TELEGRAM_API}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": build_message(lead_id),
        "disable_web_page_preview": True,
    }
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=settings.NOTIFY_TIMEOUT) as own_client:
                response = await own_client.post(url, json=payload)
        else:
            response = await client.post(url, json=payload)
        if response.status_code != 200:
            logger.error("Telegram вернул код %s для заявки #%s", response.status_code, lead_id)
            return False
        logger.info("Уведомление о заявке #%s отправлено в Telegram", lead_id)
        return True
    except Exception as exc:  # noqa: BLE001
        # str(exc) может содержать URL с токеном бота — пишем только тип ошибки.
        logger.error("Не удалось отправить Telegram о заявке #%s: %s", lead_id, exc.__class__.__name__)
        return False


async def notify_new_lead(lead_id):
    """Отправить все настроенные уведомления параллельно, ждать не дольше NOTIFY_TIMEOUT.

    Возвращает список имён каналов, по которым пытались отправить (для тестов).
    """
    jobs = {}
    if settings.EMAIL_HOST and email_recipients():
        jobs["email"] = send_email(lead_id)
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        jobs["telegram"] = send_telegram(lead_id)
    if not jobs:
        logger.info("Новая заявка #%s (уведомления не настроены)", lead_id)
        return []
    try:
        await asyncio.wait_for(
            asyncio.gather(*jobs.values(), return_exceptions=True),
            timeout=settings.NOTIFY_TIMEOUT,
        )
    except (TimeoutError, asyncio.TimeoutError):
        logger.warning("Уведомления о заявке #%s не уложились в %s с", lead_id, settings.NOTIFY_TIMEOUT)
    return list(jobs)
