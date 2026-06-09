import html
"""
operator.py — Операторський режим бота.

Команда /operator <код> — вхід в режим оператора.
Оператор бачить замовлення, може змінювати статуси.
"""

import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData

from app.api_client import list_jobs, get_job, update_job_status, download_file
from app.config import settings
from app.states import OperatorFSM

logger = logging.getLogger(__name__)
router = Router()


class OperatorCB(CallbackData, prefix="op"):
    action: str
    job_id: str = ""


def operator_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Поточні замовлення", callback_data=OperatorCB(action="list_active"))
    builder.button(text="📦 Готові (сьогодні)", callback_data=OperatorCB(action="list_ready"))
    builder.button(text="🔄 Оновити", callback_data=OperatorCB(action="refresh"))
    builder.adjust(1)
    return builder.as_markup()


def job_list_keyboard(jobs: list) -> tuple[str, any]:
    builder = InlineKeyboardBuilder()
    if not jobs:
        text = "📭 Замовлень немає"
    else:
        lines = []
        for j in jobs[:10]:  # максимум 10
            files = j.get("files", [])
            f0 = files[0] if files else {}

            # Ім'я файлу або кількість файлів
            if f0:
                file_label = html.escape(f0["original_name"][:18])
            else:
                file_label = "без файлів"

            # Сторінки
            pages = f0.get("page_count") if f0 else None
            pages_str = f"{pages}с." if pages else ""

            # Тип файлу
            mime = f0.get("mime_type", "") if f0 else ""
            if mime.startswith("image/"):
                type_icon = "🖼"
                file_type = "фото"
            elif mime in ("application/pdf",):
                type_icon = "📄"
                file_type = "PDF"
            elif "word" in mime or "odt" in mime:
                type_icon = "📝"
                file_type = "DOC"
            elif mime:
                type_icon = "📎"
                file_type = "файл"
            else:
                type_icon = "📎"
                file_type = ""

            status_emoji = {
                "draft": "📝",
                "processing": "⏳",
                "ready_to_print": "✅",
                "printed": "🖨",
                "failed": "❌",
            }.get(j["status"], "❓")

            # Час створення — показуємо дату і час
            created_raw = j.get("created_at", "")
            if created_raw:
                created = created_raw[5:16].replace("T", " ")  # "06-07 15:13"
            else:
                created = ""

            color = "🎨" if j.get("color_mode") == "color" else "⬛"
            copies = j.get("copies", 1)

            # Рядок у списку: статус + колір + код + файл + сторінки + час
            parts = [f"{status_emoji}{color}", f"`{j['id'][:8]}`", file_type, file_label]
            if pages_str:
                parts.append(pages_str)
            parts.append(f"×{copies}")
            if created:
                parts.append(created)
            lines.append(" ".join(parts))

            # Кнопка: одна на рядок — статус + код + ім'я файлу
            btn_label = f"{status_emoji} {j['id'][:8]} {type_icon}{file_type} {file_label[:10]}"
            builder.button(
                text=btn_label,
                callback_data=OperatorCB(action="detail", job_id=j["id"]),
            )
        total = len(jobs)
        text = "\n".join(lines)
        if total > 10:
            text += f"\n... та ще {total - 10} замовлень" 

    builder.button(text="◀️ Меню", callback_data=OperatorCB(action="menu"))
    builder.adjust(1)
    return text, builder.as_markup()


def job_detail_keyboard(job: dict):
    builder = InlineKeyboardBuilder()
    status = job["status"]

    if status == "draft":
        builder.button(text="🟢 Прийняти в роботу", callback_data=OperatorCB(action="set_processing", job_id=job["id"]))
        builder.button(text="🔴 Скасувати", callback_data=OperatorCB(action="set_cancelled", job_id=job["id"]))
    elif status == "processing":
        builder.button(text="🖨 Готово", callback_data=OperatorCB(action="set_printed", job_id=job["id"]))
        builder.button(text="🔴 Скасувати", callback_data=OperatorCB(action="set_cancelled", job_id=job["id"]))
    elif status == "ready_to_print":
        builder.button(text="🖨 Надруковано", callback_data=OperatorCB(action="set_printed", job_id=job["id"]))

    # Кнопки скачування файлів
    for f in job.get("files", []):
        fname = f["original_name"][:20]
        builder.button(
            text=f"📎 {fname}",
            callback_data=OperatorCB(action="get_file", job_id=f["id"]),
        )
    builder.button(text="◀️ Назад", callback_data=OperatorCB(action="list_active"))
    builder.adjust(1)
    return builder.as_markup()


def format_job_detail(job: dict) -> str:
    status_emoji = {
        "draft": "📝", "processing": "⏳",
        "ready_to_print": "✅", "printed": "🖨", "failed": "❌",
    }.get(job["status"], "❓")

    lines = [
        f"{status_emoji} <b>Замовлення</b> <code>{job['id'][:8]}...</code>",
        f"👤 User ID: <code>{job['user_id']}</code>",
        f"📊 Статус: <b>{job['status']}</b>",
        f"📋 Копій: {job['copies']} | {job['color_mode']} | {'двост.' if job['duplex'] else 'одност.'}",
        "",
        "<b>Файли:</b>",
    ]
    for f in job.get("files", []):
        pages = f.get("page_count") or "—"
        color = "🎨" if f.get("is_color") else "⬛"
        fmt = f.get("paper_format") or "—"
        status = f.get("status", "")
        lines.append(f"  {color} {html.escape(f['original_name'][:30])} — {pages} стор., {fmt} [{status}]")

    return "\n".join(lines)


# ── Хендлери ──────────────────────────────────────────────────────

@router.message(Command("operator"))
async def cmd_operator(message: Message, state: FSMContext):
    if not settings.OPERATOR_SECRET:
        await message.answer("❌ Операторський режим не налаштовано.")
        return

    parts = message.text.split(maxsplit=1)
    code = parts[1].strip() if len(parts) > 1 else ""

    if code != settings.OPERATOR_SECRET:
        await message.answer("❌ Невірний код доступу.")
        return

    await state.set_state(OperatorFSM.menu)
    await message.answer(
        "🔐 <b>Операторський режим</b>\n\nВітаємо! Оберіть дію:",
        reply_markup=operator_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(OperatorCB.filter(F.action == "menu"))
async def op_menu(query: CallbackQuery, state: FSMContext):
    await state.set_state(OperatorFSM.menu)
    await query.message.edit_text(
        "🔐 <b>Операторський режим</b>\n\nОберіть дію:",
        reply_markup=operator_menu_keyboard(),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(OperatorCB.filter(F.action.in_({"list_active", "refresh"})))
async def op_list_active(query: CallbackQuery, state: FSMContext):
    try:
        jobs_processing = await list_jobs(status_filter="processing", limit=20)
        jobs_draft = await list_jobs(status_filter="draft", limit=20)
        jobs_ready = await list_jobs(status_filter="ready_to_print", limit=20)
        all_jobs = jobs_ready + jobs_processing + jobs_draft
        # Показуємо тільки перші 10, решта — лічильник
        display = all_jobs[:10]
        text, kb = job_list_keyboard(display)
        total = len(all_jobs)
        extra = f"\n\n<i>... та ще {total - 10} замовлень</i>" if total > 10 else ""
        await query.message.edit_text(
            f"📋 <b>Поточні замовлення</b> ({total})\n\n{text}{extra}",
            reply_markup=kb,
            parse_mode="HTML",
        )
    except Exception as e:
        await query.answer(f"Помилка: {str(e)[:180]}", show_alert=True)
    await query.answer()


@router.callback_query(OperatorCB.filter(F.action == "list_ready"))
async def op_list_ready(query: CallbackQuery):
    try:
        jobs = await list_jobs(status_filter="ready_to_print", limit=20)
        text, kb = job_list_keyboard(jobs)
        await query.message.edit_text(
            f"📦 <b>Готові замовлення</b> ({len(jobs)})\n\n{text}",
            reply_markup=kb,
            parse_mode="HTML",
        )
    except Exception as e:
        await query.answer(f"Помилка: {str(e)[:180]}", show_alert=True)
    await query.answer()


@router.callback_query(OperatorCB.filter(F.action == "detail"))
async def op_job_detail(query: CallbackQuery, callback_data: OperatorCB, state: FSMContext, bot: Bot):
    try:
        job = await get_job(callback_data.job_id)
        await state.set_state(OperatorFSM.job_detail)
        await query.message.edit_text(
            format_job_detail(job),
            reply_markup=job_detail_keyboard(job),
            parse_mode="HTML",
        )
    except Exception as e:
        await query.answer(f"Помилка: {str(e)[:180]}", show_alert=True)
    await query.answer()


@router.callback_query(OperatorCB.filter(F.action.in_({"set_processing", "set_printed", "set_cancelled"})))
async def op_change_status(query: CallbackQuery, callback_data: OperatorCB, bot: Bot):
    status_map = {
        "set_processing": "processing",
        "set_printed":    "printed",
        "set_cancelled":  "failed",
    }
    new_status = status_map[callback_data.action]
    try:
        job = await update_job_status(callback_data.job_id, new_status)
        detail_text = format_job_detail(job)
        if len(detail_text) > 3800:
            detail_text = detail_text[:3800] + "\n<i>...обрізано</i>"
        await query.message.edit_text(
            detail_text,
            reply_markup=job_detail_keyboard(job),
            parse_mode="HTML",
        )
        await query.answer(f"✅ Статус змінено: {new_status}")
    except Exception as e:
        await query.answer(f"Помилка: {str(e)[:180]}", show_alert=True)

@router.callback_query(OperatorCB.filter(F.action == "get_file"))
async def op_get_file(query: CallbackQuery, callback_data: OperatorCB, bot: Bot):
    """Надсилає посилання на файл оператору."""
    try:
        url = f"https://printbot-manager.duckdns.org/instance/{settings.INSTANCE_SUBDOMAIN}/api/print/files/{callback_data.job_id}/download?api_key={settings.INSTANCE_API_KEY}"
        await bot.send_message(
            chat_id=query.from_user.id,
            text=f"📎 <a href=\"{url}\">Завантажити файл</a>",
            parse_mode="HTML",
        )
        await query.answer("✅ Посилання надіслано")
    except Exception as e:
        await query.answer(f"❌ Помилка: {e}", show_alert=True)
