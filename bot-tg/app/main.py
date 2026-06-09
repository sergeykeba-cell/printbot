"""
main.py — Точка входу бота з FSM, middleware та фоновим опитуванням.
"""

import asyncio
import os
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from app.config import settings
from app.middleware.album import AlbumMiddleware
from app.handlers import start, file_upload, config_order, operator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from app.pending import register_pending, get_all_pending, mark_notified


async def _poll_orders(bot: Bot) -> None:
    """
    Кожні 30с перевіряє статус зареєстрованих замовлень.
    Використовує GET /api/print/jobs/{job_id}.
    """
    from app.api_client import get_job
    from app.pending import get_all_pending, mark_notified
    while True:
        await asyncio.sleep(30)
        for user_id, entry in get_all_pending().items():
            if entry["notified"]:
                continue
            try:
                job = await get_job(entry["job_id"])
                status = job.get("status", "")
                if status in ("ready_to_print", "printed"):
                    await bot.send_message(
                        user_id,
                        f"✅ Ваше замовлення <code>{entry['job_id'][:8]}</code> готове!\n"
                        f"Звертайтесь до оператора.",
                        parse_mode="HTML",
                    )
                    mark_notified(user_id)
                elif status == "failed":
                    await bot.send_message(
                        user_id,
                        f"❌ Помилка обробки замовлення <code>{entry['job_id'][:8]}</code>.\n"
                        f"Зверніться до оператора.",
                        parse_mode="HTML",
                    )
                    mark_notified(user_id)
            except Exception as e:
                logger.warning("Poll помилка user=%s job=%s: %s", user_id, entry["job_id"], e)


async def main():
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    redis_storage = RedisStorage.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/1"))
    dp = Dispatcher(storage=redis_storage)

    dp.message.middleware(AlbumMiddleware())

    dp.include_router(config_order.router)
    dp.include_router(operator.router)
    dp.include_router(file_upload.router)
    dp.include_router(start.router)

    async def on_startup(**kwargs):
        asyncio.create_task(_poll_orders(kwargs["bot"]))
        logger.info("Бот запущено: %s", settings.SHOP_NAME)

    dp.startup.register(on_startup)

    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
