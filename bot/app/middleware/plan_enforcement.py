"""
plan_enforcement.py — Middleware обмеження Free-тарифу.

Перехоплює POST /api/v1/orders.
Для free-тарифу рахує замовлення за місяць і блокує при перевищенні ліміту.
Кешує конфігурацію з TTL 5 хвилин. При відмові зовнішнього API — stale або 503.
"""
import os
import logging
from datetime import datetime, timezone

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.cache import instance_config_cache
from app.database import AsyncSessionLocal

logger = logging.getLogger("middleware.plan")

INTERNAL_CONFIG_URL = os.environ.get(
    "INTERNAL_CONFIG_URL",
    "http://localhost:8000/api/v1/internal/config",
)
INSTANCE_ID = os.environ.get("INSTANCE_ID", "default")


async def _fetch_config() -> dict | None:
    """Завантажує конфігурацію з внутрішнього ендпоінту."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(INTERNAL_CONFIG_URL)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning(f"[plan] Не вдалося завантажити config: {e}")
    return None


async def _get_config() -> dict | None:
    """
    Отримує конфігурацію з кешу або завантажує свіжу.
    При відмові — stale fallback. Якщо кешу немає — None (→ 503).
    """
    cached = await instance_config_cache.get(INSTANCE_ID)
    if cached:
        return cached

    fresh = await _fetch_config()
    if fresh:
        await instance_config_cache.set(INSTANCE_ID, fresh)
        return fresh

    # Stale fallback
    stale = await instance_config_cache.get_stale(INSTANCE_ID)
    if stale:
        logger.warning("[plan] Використовуємо застарілі дані конфігурації (stale).")
        return stale

    return None


async def _count_month_orders() -> int:
    """Рахує замовлення за поточний календарний місяць."""
    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    async with AsyncSessionLocal() as db:
        result = await db.scalar(
            text(
                "SELECT COUNT(*) FROM print_jobs "
                "WHERE created_at >= :start_of_month"
            ),
            {"start_of_month": start_of_month},
        )
    return result or 0


class PlanEnforcementMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Перехоплюємо лише POST /api/v1/orders (точний шлях)
        if not (request.method == "POST" and request.url.path == "/api/v1/orders"):
            return await call_next(request)

        config = await _get_config()

        if config is None:
            logger.error("[plan] Конфігурація недоступна — блокуємо запит (503).")
            return JSONResponse(
                status_code=503,
                content={
                    "error": "SERVICE_UNAVAILABLE",
                    "message": "Конфігурація тарифу тимчасово недоступна.",
                },
            )

        plan_tier = config.get("plan_tier", "free")
        if plan_tier != "free":
            return await call_next(request)

        max_orders   = config.get("max_orders_per_month", 30)
        bonus_orders = config.get("bonus_orders", 0)
        effective_limit = max_orders + bonus_orders

        month_orders = await _count_month_orders()

        if month_orders >= effective_limit:
            subdomain = config.get("subdomain", "unknown")
            logger.info(
                f"[plan] LIMIT_REACHED subdomain={subdomain} "
                f"usage={month_orders} limit={effective_limit}"
            )
            return JSONResponse(
                status_code=402,
                content={
                    "error": "LIMIT_REACHED",
                    "message": "Місячний ліміт замовлень вичерпано. Будь ласка, оновіть тарифний план.",
                    "upgrade_url": f"https://printbot.app/upgrade?sub={subdomain}",
                    "current_usage": month_orders,
                    "limit": effective_limit,
                },
            )

        return await call_next(request)
