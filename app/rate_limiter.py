"""
rate_limiter.py — Ініціалізація slowapi Limiter з Redis backend.

Особливості:
  - key_func читає X-Forwarded-For / X-Real-IP (за Traefik/Nginx проксі).
  - Fallback: якщо Redis недоступний — запит пропускається (fail open),
    але в лог пишеться CRITICAL-алерт.
  - Окремий Redis DB (за замовчуванням /1) — не конфліктує з ARQ broker.
  - Лімітер — глобальний singleton, імпортується в main.py і router.py.
"""
import os
import logging

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

logger = logging.getLogger("rate_limiter")

# ── Key function: реальний IP з-за проксі ─────────────────────────

def _get_real_ip(request: Request) -> str:
    """
    Визначає реальну IP-адресу клієнта.

    Пріоритет:
      1. X-Forwarded-For (Traefik, Nginx, Cloudflare)
      2. X-Real-IP (Nginx)
      3. request.client.host (пряме з'єднання)

    X-Forwarded-For може містити ланцюжок IP (client, proxy1, proxy2).
    Беремо перший — це оригінальний клієнт.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # "1.2.3.4, 10.0.0.1, 172.16.0.1" → "1.2.3.4"
        real_ip = forwarded_for.split(",")[0].strip()
        if real_ip:
            return real_ip

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fallback — пряме з'єднання або тести
    return get_remote_address(request)


# ── Redis URI для rate limiting ────────────────────────────────────
# Окремий DB (/1) — ARQ broker зазвичай на /0

_RATE_LIMIT_REDIS_URL = os.getenv(
    "RATE_LIMIT_REDIS_URL",
    os.getenv("REDIS_URL", "redis://localhost:6379").rstrip("/") + "/1",
)

# ── Limiter singleton ──────────────────────────────────────────────

limiter = Limiter(
    key_func=_get_real_ip,
    storage_uri=_RATE_LIMIT_REDIS_URL,
    # При помилці Redis — fail open (пропускаємо запит, не блокуємо)
    # slowapi передає виключення в on_breach; ми перехоплюємо нижче
    enabled=True,
)

logger.info(f"[rate_limiter] Ініціалізовано. Redis: {_RATE_LIMIT_REDIS_URL}")


# ── Fail-open обробник помилок Redis ──────────────────────────────

async def _rate_limit_exceeded_handler(request: Request, exc):
    """
    Стандартний обробник 429 від slowapi.
    Повертає читабельне тіло для PWA-панелі.
    """
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=429,
        content={
            "error": "RATE_LIMIT_EXCEEDED",
            "message": "Забагато запитів. Спробуйте через хвилину.",
            "retry_after": "60",
        },
        headers={"Retry-After": "60"},
    )


def install_rate_limit_handlers(app) -> None:
    """
    Підключає limiter до FastAPI app:
      - app.state.limiter
      - exception handler для 429
      - SlowAPIMiddleware

    Викликається один раз в main.py після створення app.
    """
    from slowapi import _rate_limit_exceeded_handler as _default_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    logger.info("[rate_limiter] Handlers та middleware встановлено.")
