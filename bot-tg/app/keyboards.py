"""
keyboards.py — Inline клавіатури для карточки замовлення.
"""

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


class PrintCB(CallbackData, prefix="print"):
    action: str
    value: str = ""


def order_card_keyboard(opts: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    file_type = opts.get("file_type", "doc")

    # Колір
    color_label = "🟢 Кольоровий" if opts["color_mode"] == "color" else "⚪️ Чорно-білий"
    builder.button(text=color_label, callback_data=PrintCB(action="toggle_color"))

    if file_type == "photo":
        # Розміри фото друку
        for size in ["10×15", "13×18", "15×21", "20×30"]:
            mark = "✅ " if opts.get("photo_size") == size else ""
            builder.button(
                text=f"{mark}{size}",
                callback_data=PrintCB(action="set_photo_size", value=size),
            )
    else:
        # Двосторонній
        duplex_label = "🟢 Двосторонній" if opts["duplex"] else "⚪️ Односторонній"
        builder.button(text=duplex_label, callback_data=PrintCB(action="toggle_duplex"))

        # Формат паперу
        a4_mark = "✅ " if opts["paper_format"] == "A4" else ""
        a3_mark = "✅ " if opts["paper_format"] == "A3" else ""
        builder.button(text=f"{a4_mark}A4", callback_data=PrintCB(action="set_format", value="A4"))
        builder.button(text=f"{a3_mark}A3", callback_data=PrintCB(action="set_format", value="A3"))

        # Орієнтація
        portrait_mark = "✅ " if opts.get("orientation", "portrait") == "portrait" else ""
        landscape_mark = "✅ " if opts.get("orientation", "portrait") == "landscape" else ""
        builder.button(text=f"{portrait_mark}📄 Книжна", callback_data=PrintCB(action="set_orientation", value="portrait"))
        builder.button(text=f"{landscape_mark}📰 Альбомна", callback_data=PrintCB(action="set_orientation", value="landscape"))

    # Кількість копій
    builder.button(text=f"📋 Копій: {opts['copies']}", callback_data=PrintCB(action="change_copies"))

    # Підтвердити
    builder.button(text="✅ Підтвердити замовлення", callback_data=PrintCB(action="confirm"))

    if file_type == "photo":
        builder.adjust(1, 2, 2, 1, 1)
    else:
        builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()


def order_card_text(opts: dict, job_id: str, file_name: str) -> str:
    """Текст карточки замовлення."""
    color = "🎨 Кольоровий" if opts["color_mode"] == "color" else "⬛ Чорно-білий"
    pages_info = f"{opts.get('page_count', '—')} стор." if opts.get("page_count") else "визначається..."
    file_type = opts.get("file_type", "doc")

    if file_type == "photo":
        photo_size = opts.get("photo_size", "10×15")
        return (
            f"🖼 *{file_name}*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📐 Розмір друку: {photo_size} см\n"
            f"🖨 Режим: {color}\n"
            f"📋 Копій: {opts['copies']}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🔖 Замовлення: `{job_id[:8]}...`\n\n"
            f"_Натисніть кнопки для зміни параметрів_"
        )
    else:
        duplex = "↔️ Двосторонній" if opts["duplex"] else "➡️ Односторонній"
        orientation = "📄 Книжна" if opts.get("orientation", "portrait") == "portrait" else "📰 Альбомна"
        return (
            f"📄 *{file_name}*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📊 Сторінок: {pages_info}\n"
            f"📐 Формат: {opts['paper_format']} | {orientation}\n"
            f"🖨 Режим: {color}\n"
            f"📑 Друк: {duplex}\n"
            f"📋 Копій: {opts['copies']}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🔖 Замовлення: `{job_id[:8]}...`\n\n"
            f"_Натисніть кнопки для зміни параметрів_"
        )
