"""
file_upload.py — Обробка вхідних файлів та фото.
"""

import logging
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.api_client import create_job, upload_file, get_job
from app.config import settings
from app.states import OrderFSM
from app.handlers.config_order import show_order_card

logger = logging.getLogger(__name__)
router = Router()

SUPPORTED_EXTENSIONS = {".pdf", ".doc", ".docx", ".odt", ".png", ".jpg", ".jpeg"}
TMP_DIR = Path("/tmp/printbot")
TMP_DIR.mkdir(exist_ok=True)


async def _process_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    file_id: str,
    file_name: str,
    file_size: int,
    suffix: str,
    file_type: str = "doc",
) -> None:
    """Спільна логіка завантаження файлу."""
    if file_size > settings.MAX_FILE_SIZE:
        await message.answer(
            f"❌ Файл занадто великий ({file_size // 1024 // 1024} МБ).\n"
            f"Максимум: 50 МБ."
        )
        return

    if suffix not in SUPPORTED_EXTENSIONS:
        await message.answer(
            f"❌ Формат *{suffix}* не підтримується.\n"
            f"Підтримувані: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
            parse_mode="Markdown",
        )
        return

    status_msg = await message.answer("⏳ Завантажую файл...")
    tmp_path = TMP_DIR / f"{message.from_user.id}_{file_id}{suffix}"

    try:
        # Завантажуємо з Telegram
        tg_file = await bot.get_file(file_id)
        await bot.download_file(tg_file.file_path, tmp_path)

        # Створюємо замовлення
        job = await create_job(user_id=message.from_user.id)
        job_id = job["id"]

        # Завантажуємо файл в API
        await status_msg.edit_text("📤 Обробляю файл...")
        result = await upload_file(job_id, tmp_path, file_name)

        # Чекаємо поки воркер обробить файл (до 15с)
        import asyncio as _asyncio
        from app.api_client import get_job as _get_job
        page_count = None
        is_color = False
        paper_format = "A4"

        for _ in range(10):
            await _asyncio.sleep(1.5)
            try:
                job_data = await _get_job(job_id)
                files = job_data.get("files", [])
                if files and files[0].get("status") in ("ready_to_print", "failed"):
                    f = files[0]
                    page_count = f.get("page_count")
                    is_color = f.get("is_color", False)
                    paper_format = f.get("paper_format") or "A4"
                    break
            except Exception:
                pass

        await status_msg.delete()

        # Показуємо карточку замовлення
        await show_order_card(
            message=message,
            state=state,
            job_id=job_id,
            file_name=file_name,
            page_count=page_count,
            is_color=is_color,
            paper_format=paper_format,
            file_type=file_type,
        )

        logger.info(
            "Файл завантажено: user=%s job=%s file=%s",
            message.from_user.id, job_id, file_name,
        )

    except Exception as e:
        logger.error("Помилка завантаження файлу: %s", e)
        await status_msg.edit_text(
            "❌ Сталась помилка при обробці файлу.\n"
            "Спробуйте ще раз або зверніться до оператора."
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@router.message(F.document)
async def handle_document(message: Message, bot: Bot, state: FSMContext, album: list = None):
    """Обробник документів (з підтримкою альбомів)."""
    messages = album or [message]

    for msg in messages:
        doc = msg.document
        suffix = Path(doc.file_name or "").suffix.lower()
        file_type = "photo" if suffix in {".jpg", ".jpeg", ".png", ".webp", ".heic"} else "doc"
        await _process_file(
            message=msg,
            bot=bot,
            state=state,
            file_id=doc.file_id,
            file_name=doc.file_name or "document",
            file_size=doc.file_size or 0,
            suffix=suffix,
            file_type=file_type,
        )


@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot, state: FSMContext, album: list = None):
    """Обробник фото."""
    messages = album or [message]

    for msg in messages:
        photo = msg.photo[-1]
        await _process_file(
            message=msg,
            bot=bot,
            state=state,
            file_id=photo.file_id,
            file_name=f"photo_{photo.file_id}.jpg",
            file_size=photo.file_size or 0,
            suffix=".jpg",
            file_type="photo",
        )
