"""
Генерация демонстрационных PDF-документов (для демо-версии сайта).

Каждый PDF содержит:
- крупную надпись «ДЕМО-ДОКУМЕНТ» (чтобы никто не принял файл за настоящий);
- название документа, организацию, номер и дату;
- штамп «Документ подписан простой электронной подписью: <кто>, <дата>».

Текст выводится настоящим шрифтом (а не картинкой), поэтому в PDF работает
поиск и копирование — как требует п. 22–26 Требований к сайту.

Нужен TTF-шрифт с кириллицей. Путь берётся из settings.PDF_FONT_PATH,
если файла нет — пробуем другие типовые пути (в Docker: пакет fonts-dejavu-core).
"""

import io
import logging
import os
from datetime import date, datetime

from django.conf import settings
from django.utils import timezone
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

FONT_NAME = "DemoSans"
FALLBACK_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

_font_ready = None  # кеш: имя зарегистрированного шрифта


def find_font_path():
    """Первый существующий шрифт: settings.PDF_FONT_PATH, затем запасные пути."""
    candidates = [getattr(settings, "PDF_FONT_PATH", "")] + FALLBACK_FONT_PATHS
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def get_font():
    """Зарегистрировать TTF-шрифт в reportlab (один раз) и вернуть его имя.

    Если шрифт с кириллицей не найден — Helvetica (кириллица будет нечитаема)
    и предупреждение в логе: установите fonts-dejavu-core или задайте PDF_FONT_PATH.
    """
    global _font_ready
    if _font_ready:
        return _font_ready
    path = find_font_path()
    if path:
        pdfmetrics.registerFont(TTFont(FONT_NAME, path))
        _font_ready = FONT_NAME
    else:
        logger.warning(
            "Не найден TTF-шрифт с кириллицей для PDF. Установите пакет fonts-dejavu-core "
            "или укажите путь в переменной PDF_FONT_PATH. Сейчас используется Helvetica."
        )
        _font_ready = "Helvetica"
    return _font_ready


def _fmt_date(value):
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value or "")


def _wrap(text, font, size, max_width):
    """Разбить текст на строки, помещающиеся в max_width (по словам)."""
    lines = []
    for paragraph in str(text).splitlines() or [""]:
        words = paragraph.split()
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if pdfmetrics.stringWidth(candidate, font, size) <= max_width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        lines.append(line)
    return lines


def generate_demo_pdf(title, *, org_name="", number="", doc_date=None, signer="", signed_at=None, body=""):
    """Создать демо-PDF и вернуть его содержимое (bytes)."""
    font = get_font()
    buffer = io.BytesIO()
    width, height = A4
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"ДЕМО — {title}")
    pdf.setAuthor(org_name or "Демо-организация")
    pdf.setSubject("Демонстрационный документ, данные вымышлены")

    left = 20 * mm
    max_width = width - 40 * mm

    # Фон шапки и рамка страницы — рисунок, а не текст: диагональная надпись-водяной знак
    # «ломала» бы порядок текста при поиске и копировании, поэтому её не делаем.
    pdf.setFillColor(Color(0.85, 0.1, 0.1, alpha=0.08))
    pdf.rect(0, height - 40 * mm, width, 40 * mm, stroke=0, fill=1)
    pdf.setStrokeColor(HexColor("#b3261e"))
    pdf.setLineWidth(2)
    pdf.rect(8 * mm, 8 * mm, width - 16 * mm, height - 16 * mm, stroke=1, fill=0)

    # Шапка: крупно «ДЕМО-ДОКУМЕНТ».
    y = height - 25 * mm
    pdf.setFillColor(HexColor("#b3261e"))
    pdf.setFont(font, 32)
    pdf.drawString(left, y, "ДЕМО-ДОКУМЕНТ")
    y -= 8 * mm
    pdf.setFont(font, 10)
    pdf.drawString(left, y, "Демонстрационный образец. Организация и все данные вымышлены.")

    pdf.setFillColor(HexColor("#1f1f1f"))
    if org_name:
        y -= 14 * mm
        pdf.setFont(font, 11)
        for line in _wrap(org_name, font, 11, max_width):
            pdf.drawString(left, y, line)
            y -= 5.5 * mm

    y -= 10 * mm
    pdf.setFont(font, 18)
    for line in _wrap(title, font, 18, max_width):
        pdf.drawString(left, y, line)
        y -= 8 * mm

    details = []
    if number:
        details.append(f"№ {number}")
    if doc_date:
        details.append(f"от {_fmt_date(doc_date)}")
    if details:
        pdf.setFont(font, 12)
        pdf.drawString(left, y, " ".join(details))
        y -= 10 * mm

    pdf.setFont(font, 11)
    text = body or (
        "Это демонстрационный файл, созданный автоматически для показа работы сайта. "
        "На рабочем сайте здесь размещается подлинный документ образовательной организации "
        "в формате PDF с текстовым слоем, подписанный простой электронной подписью."
    )
    for line in _wrap(text, font, 11, max_width):
        pdf.drawString(left, y, line)
        y -= 6 * mm

    # Штамп электронной подписи (внизу страницы).
    if signer:
        box_w, box_h = max_width, 26 * mm
        box_y = 25 * mm
        pdf.setStrokeColor(HexColor("#1a56a8"))
        pdf.setLineWidth(1.2)
        pdf.roundRect(left, box_y, box_w, box_h, 3 * mm)
        pdf.setFillColor(HexColor("#1a56a8"))
        pdf.setFont(font, 11)
        pdf.drawString(left + 5 * mm, box_y + box_h - 8 * mm, "Документ подписан простой электронной подписью")
        pdf.setFont(font, 10)
        pdf.drawString(left + 5 * mm, box_y + box_h - 15 * mm, f"Подписант: {signer}")
        pdf.drawString(
            left + 5 * mm,
            box_y + box_h - 21 * mm,
            f"Дата подписания: {_fmt_date(signed_at or doc_date or timezone.now())}",
        )

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
