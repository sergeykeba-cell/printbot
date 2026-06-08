"""
start.py — Обробник /start та загальних повідомлень.
"""

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.api_client import get_job
from app.config import settings
from app.states import OrderFSM

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.set_state(OrderFSM.waiting_for_file)
    await message.answer(
        f"👋 Вітаємо у *{settings.SHOP_NAME}*!\n\n"
        "📄 Надішліть файл для друку.\n"
        "Підтримувані формати: PDF, DOCX, DOC, ODT, PNG, JPG\n"
        "Максимальний розмір: 50 МБ\n\n"
        "Після отримання файлу ви побачите карточку замовлення "
        "з параметрами які можна налаштувати.",
        parse_mode="Markdown",
    )


@router.message(Command("status"))
async def cmd_status(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Використання: /status JOB_ID")
        return

    job_id = parts[1].strip()
    try:
        job = await get_job(job_id)
        status_emoji = {
            "draft": "📝",
            "processing": "⏳",
            "ready_to_print": "✅",
            "printed": "🖨",
            "failed": "❌",
        }.get(job["status"], "❓")

        files_info = ""
        for f in job.get("files", []):
            pages = f.get("page_count") or "—"
            color = "кольоровий" if f.get("is_color") else "ч/б"
            fmt = f.get("paper_format") or "—"
            files_info += f"\n  📎 {f['original_name']}: {pages} стор., {color}, {fmt}"

        await message.answer(
            f"{status_emoji} Замовлення `{job_id[:8]}...`\n"
            f"Статус: *{job['status']}*\n"
            f"Копій: {job['copies']}, {job['color_mode']}"
            f"{files_info}",
            parse_mode="Markdown",
        )
    except Exception:
        await message.answer("❌ Замовлення не знайдено.")


@router.message()
async def handle_other(message: Message):
    await message.answer(
        "📄 Надішліть файл або фото для друку.\n"
        "Підтримувані формати: PDF, DOCX, DOC, ODT, PNG, JPG"
    )
