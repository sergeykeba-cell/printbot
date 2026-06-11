"""
notify.py — Telegram-сповіщення адміну інстансу з агрегацією через Redis.
"""
import asyncio
import logging
import os

import aiohttp
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
ALERT_PREFIX = "alert_agg:"


def _get_redis_client() -> aioredis.Redis:
    url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    return aioredis.from_url(url, decode_responses=True)


async def _send_telegram_message(text: str) -> None:
    """Низькорівнева відправка в Telegram."""
    if os.environ.get("ALERTS_ENABLED", "true").lower() != "true":
        logger.debug("_send_telegram_message: алерти вимкнені (ALERTS_ENABLED=false).")
        return

    token = os.environ.get("TG_BOT_TOKEN", "")
    admin_id = os.environ.get("ADMIN_TELEGRAM_ID", "")

    if not token or not admin_id:
        logger.debug("_send_telegram_message: TG_BOT_TOKEN або ADMIN_TELEGRAM_ID не задані.")
        return

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    payload = {"chat_id": admin_id, "text": text, "parse_mode": "HTML"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("_send_telegram_message: Telegram API повернув %d: %s", resp.status, body)
    except Exception as e:
        logger.warning("_send_telegram_message: помилка надсилання: %s", e)


async def send_admin_alert(text: str) -> None:
    """Прямий алерт без агрегації (для некритичних разових подій)."""
    await _send_telegram_message(text)


async def send_aggregated_alert(alert_key: str, message: str, cooldown_seconds: int = 600) -> None:
    """
    Надсилає алерт при першому виникненні, далі лише інкрементує лічильник у Redis.
    Повторний алерт — тільки через flush_aggregated_alerts().
    """
    key = f"{ALERT_PREFIX}{alert_key}"
    try:
        r = _get_redis_client()
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, cooldown_seconds)
            await _send_telegram_message(message)
        await r.aclose()
    except Exception as e:
        logger.warning("send_aggregated_alert: помилка Redis: %s", e)
        # Fallback — надсилаємо напряму щоб не втратити алерт
        await _send_telegram_message(
            f"⚠️ Redis недоступний, алерти деградовані\n<code>{e}</code>"
        )
        await _send_telegram_message(message)


async def flush_aggregated_alerts() -> None:
    """
    Періодично викликається для надсилання зведення накопичених помилок.
    Скидає лічильники після відправки.
    """
    try:
        r = _get_redis_client()
        keys = await r.keys(f"{ALERT_PREFIX}*")
        for key in keys:
            count = await r.get(key)
            if count and int(count) > 1:
                alert_name = key[len(ALERT_PREFIX):]
                await _send_telegram_message(
                    f"⚠️ <b>Агрегований алерт</b>\n"
                    f"Подія: <code>{alert_name}</code>\n"
                    f"Повторень за останній період: <b>{count}</b>"
                )
            await r.delete(key)
        await r.aclose()
    except Exception as e:
        logger.warning("flush_aggregated_alerts: помилка: %s", e)


QUEUE_OVERFLOW_THRESHOLD = 50


async def _check_queue_size() -> None:
    """Перевіряє розмір черги ARQ і надсилає алерт якщо переповнена."""
    try:
        r = _get_redis_client()
        # ARQ зберігає задачі в ключі arq:queue
        queue_len = await r.llen("arq:queue")
        await r.aclose()
        if queue_len >= QUEUE_OVERFLOW_THRESHOLD:
            await send_aggregated_alert(
                "queue_overflow",
                f"⚠️ <b>Черга ARQ переповнена</b>\nЗадач у черзі: <b>{queue_len}</b> (поріг: {QUEUE_OVERFLOW_THRESHOLD})"
            )
    except Exception as e:
        logger.warning("_check_queue_size: помилка: %s", e)


async def _periodic_flush(interval_seconds: int = 600) -> None:
    """Фоновий loop для flush — запускається при старті воркера."""
    while True:
        await asyncio.sleep(interval_seconds)
        await flush_aggregated_alerts()
        await _check_queue_size()
