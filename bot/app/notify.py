"""
notify.py — Telegram-сповіщення адміну інстансу.
"""
import logging
import os
import aiohttp

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


async def send_admin_alert(text: str) -> None:
    """
    Надсилає повідомлення адміну в Telegram.
    Якщо ADMIN_TELEGRAM_ID або TG_BOT_TOKEN не задані — тихо ігнорує.
    """
    token = os.environ.get("TG_BOT_TOKEN", "")
    admin_id = os.environ.get("ADMIN_TELEGRAM_ID", "")

    if not token or not admin_id:
        logger.debug("send_admin_alert: ADMIN_TELEGRAM_ID або TG_BOT_TOKEN не задані, пропускаємо.")
        return

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    payload = {
        "chat_id": admin_id,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("send_admin_alert: Telegram API повернув %d: %s", resp.status, body)
    except Exception as e:
        logger.warning("send_admin_alert: помилка надсилання: %s", e)
