"""
config_order.py — FSM логіка карточки замовлення.

Стани:
  configuring   — карточка показана, inline кнопки
  typing_copies — ручний ввід копій текстом
"""

import logging
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.states import OrderFSM
from app.keyboards import PrintCB, order_card_keyboard, order_card_text
from app.api_client import update_job

logger = logging.getLogger(__name__)
router = Router()


def _default_opts() -> dict:
    return {
        "color_mode": "bw",
        "duplex": False,
        "paper_format": "A4",
        "copies": 1,
        "page_count": None,
    }


async def show_order_card(
    message: Message,
    state: FSMContext,
    job_id: str,
    file_name: str,
    page_count: int | None = None,
    is_color: bool = False,
    paper_format: str = "A4",
    file_type: str = "doc",
) -> None:
    """
    Показує карточку замовлення і переводить в стан configuring.
    Викликається з file_upload.py після успішного завантаження.
    """
    opts = _default_opts()
    opts["color_mode"] = "color" if is_color else "bw"
    opts["paper_format"] = paper_format or "A4"
    opts["page_count"] = page_count
    opts["file_type"] = file_type
    opts["photo_size"] = "10×15"
    opts["orientation"] = "portrait"

    await state.set_state(OrderFSM.configuring)
    await state.update_data(
        job_id=job_id,
        file_name=file_name,
        print_options=opts,
    )

    sent = await message.answer(
        order_card_text(opts, job_id, file_name),
        reply_markup=order_card_keyboard(opts),
        parse_mode="Markdown",
    )
    # Зберігаємо message_id для edit_text
    await state.update_data(card_message_id=sent.message_id)


async def _refresh_card(query: CallbackQuery, state: FSMContext) -> None:
    """Перемальовує карточку з поточними параметрами."""
    data = await state.get_data()
    opts = data["print_options"]
    job_id = data["job_id"]
    file_name = data["file_name"]

    await query.message.edit_text(
        order_card_text(opts, job_id, file_name),
        reply_markup=order_card_keyboard(opts),
        parse_mode="Markdown",
    )


# ── Обробники CallbackData ─────────────────────────────────────────

@router.callback_query(PrintCB.filter(F.action == "toggle_color"), OrderFSM.configuring)
async def toggle_color(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    opts = data["print_options"]
    opts["color_mode"] = "color" if opts["color_mode"] == "bw" else "bw"
    await state.update_data(print_options=opts)
    await _refresh_card(query, state)
    await query.answer()


@router.callback_query(PrintCB.filter(F.action == "toggle_duplex"), OrderFSM.configuring)
async def toggle_duplex(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    opts = data["print_options"]
    opts["duplex"] = not opts["duplex"]
    await state.update_data(print_options=opts)
    await _refresh_card(query, state)
    await query.answer()


@router.callback_query(PrintCB.filter(F.action == "set_format"), OrderFSM.configuring)
async def set_format(query: CallbackQuery, callback_data: PrintCB, state: FSMContext):
    data = await state.get_data()
    opts = data["print_options"]
    opts["paper_format"] = callback_data.value
    await state.update_data(print_options=opts)
    await _refresh_card(query, state)
    await query.answer()


@router.callback_query(PrintCB.filter(F.action == "set_orientation"), OrderFSM.configuring)
async def set_orientation(query: CallbackQuery, callback_data: PrintCB, state: FSMContext):
    data = await state.get_data()
    opts = data["print_options"]
    opts["orientation"] = callback_data.value
    await state.update_data(print_options=opts)
    await _refresh_card(query, state)
    await query.answer()

@router.callback_query(PrintCB.filter(F.action == "set_photo_size"), OrderFSM.configuring)
async def set_photo_size(query: CallbackQuery, callback_data: PrintCB, state: FSMContext):
    data = await state.get_data()
    opts = data["print_options"]
    opts["photo_size"] = callback_data.value
    await state.update_data(print_options=opts)
    await _refresh_card(query, state)
    await query.answer()

@router.callback_query(PrintCB.filter(F.action == "change_copies"), OrderFSM.configuring)
async def change_copies_prompt(query: CallbackQuery, state: FSMContext):
    """Переходимо в стан typing_copies — чекаємо текстовий ввід."""
    await state.set_state(OrderFSM.typing_copies)
    await query.message.answer(
        "✏️ Введіть кількість копій (1–999):"
    )
    await query.answer()


@router.message(OrderFSM.typing_copies)
async def receive_copies(message: Message, state: FSMContext):
    """Обробка введеної кількості копій."""
    text = message.text.strip() if message.text else ""

    if not text.isdigit() or not (1 <= int(text) <= 999):
        await message.answer("❌ Введіть число від 1 до 999:")
        return

    data = await state.get_data()
    opts = data["print_options"]
    opts["copies"] = int(text)
    await state.update_data(print_options=opts)
    await state.set_state(OrderFSM.configuring)

    # Перемальовуємо карточку
    await message.answer(
        order_card_text(opts, data["job_id"], data["file_name"]),
        reply_markup=order_card_keyboard(opts),
        parse_mode="Markdown",
    )


@router.callback_query(PrintCB.filter(F.action == "confirm"), OrderFSM.configuring)
async def confirm_order(query: CallbackQuery, state: FSMContext, bot: Bot):
    """Підтвердження замовлення — відправляємо параметри в API."""
    data = await state.get_data()
    opts = data["print_options"]
    job_id = data["job_id"]

    try:
        logger.info("Підтвердження opts: %s", opts)
        await update_job(job_id, opts)
        await state.set_state(OrderFSM.awaiting_payment)

        await query.message.edit_text(
            f"✅ *Замовлення підтверджено!*\n\n"
            f"🔖 Номер: `{job_id[:8]}...`\n"
            f"📋 Копій: {opts['copies']}\n"
            f"🖨 Режим: {'кольоровий' if opts['color_mode'] == 'color' else 'ч/б'}\n"
            f"📑 Друк: {'двосторонній' if opts['duplex'] else 'односторонній'}\n"
            f"📐 Формат: {opts['paper_format']}\n\n"
            f"⏳ Ваше замовлення передано оператору.\n"
            f"Ми повідомимо вас коли воно буде готове.",
            parse_mode="Markdown",
        )
        await query.answer("✅ Замовлення підтверджено!")
        logger.info("Замовлення підтверджено: job_id=%s", job_id)

    except Exception as e:
        logger.error("Помилка підтвердження: %s", e)
        await query.answer("❌ Помилка. Спробуйте ще раз.", show_alert=True)
