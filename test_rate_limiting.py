"""
test_rate_limiting.py — тести rate limiting через slowapi.

Використовує in-memory storage (замість Redis) для ізольованих тестів.
Мокуємо limiter.storage щоб не потребувати реального Redis.

Тест-кейси:
  1. Запити нижче ліміту — всі 200
  2. Перевищення ліміту — 429
  3. Різні IP — незалежні лічильники
  4. X-Forwarded-For — використовується як ключ
  5. X-Real-IP — fallback якщо немає X-Forwarded-For
  6. Ланцюжок X-Forwarded-For — береться перший IP
  7. 429 відповідь має правильний формат і заголовок Retry-After
  8. /api/print/upload — окремий ліміт 10/minute
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# ── Мокуємо зовнішні залежності до імпорту app-модулів ───────────
import sys

# Мок для app.database
db_mock = MagicMock()
db_mock.get_db = AsyncMock()
db_mock.get_redis_pool = AsyncMock()
db_mock.init_db = AsyncMock()
db_mock.init_redis = AsyncMock()
db_mock.close_redis = AsyncMock()
db_mock.AsyncSessionLocal = MagicMock()
sys.modules["app.database"] = db_mock

# Мок для app.models
models_mock = MagicMock()
sys.modules["app.models"] = models_mock

# Мок для app.schemas
schemas_mock = MagicMock()
schemas_mock.ALLOWED_EXTENSIONS = {".pdf", ".jpg"}
schemas_mock.ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg"}
schemas_mock.MAX_FILE_SIZE = 10 * 1024 * 1024
sys.modules["app.schemas"] = schemas_mock

# Мок для app.middleware
middleware_mock = MagicMock()
sys.modules["app.middleware"] = middleware_mock
sys.modules["app.middleware.plan_enforcement"] = MagicMock()

# Мок для app.api
sys.modules["app.api"] = MagicMock()
sys.modules["app.api.internal"] = MagicMock()

# Мок для app.core.tenant (якщо є)
tenant_mock = MagicMock()
sys.modules["app.core"] = MagicMock()
sys.modules["app.core.tenant"] = tenant_mock


# ── Helpers ───────────────────────────────────────────────────────

from limits.storage import MemoryStorage
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


def _get_real_ip(request: Request) -> str:
    """Та сама функція що і в rate_limiter.py."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        real_ip = forwarded_for.split(",")[0].strip()
        if real_ip:
            return real_ip
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return get_remote_address(request)


def make_test_app(limit_string: str = "5/minute") -> tuple[FastAPI, Limiter]:
    """
    Створює мінімальний FastAPI-застосунок з rate limiting.
    Використовує MemoryStorage — не потребує Redis.
    """
    test_limiter = Limiter(
        key_func=_get_real_ip,
        storage_uri="memory://",
    )

    app = FastAPI()
    app.state.limiter = test_limiter

    async def _429_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": "Забагато запитів. Спробуйте через хвилину.",
                "retry_after": "60",
            },
            headers={"Retry-After": "60"},
        )

    app.add_exception_handler(RateLimitExceeded, _429_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.post("/api/print/jobs")
    @test_limiter.limit(limit_string)
    async def create_job(request: Request):
        return {"status": "created"}

    @app.post("/api/print/upload")
    @test_limiter.limit("3/minute")  # Менший ліміт для тесту швидкості
    async def upload_file(request: Request):
        return {"status": "uploaded"}

    return app, test_limiter


# ── Тести ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_requests_below_limit_pass():
    """Тест 1: Запити нижче ліміту — всі 200."""
    app, _ = make_test_app("5/minute")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Forwarded-For": "1.2.3.4"},
    ) as client:
        for i in range(5):
            resp = await client.post("/api/print/jobs")
            assert resp.status_code == 200, f"Запит {i+1} провалився: {resp.status_code}"


@pytest.mark.asyncio
async def test_requests_above_limit_return_429():
    """Тест 2: Перевищення ліміту — 429."""
    app, _ = make_test_app("3/minute")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Forwarded-For": "2.2.2.2"},
    ) as client:
        # Перші 3 — OK
        for i in range(3):
            resp = await client.post("/api/print/jobs")
            assert resp.status_code == 200, f"Запит {i+1} мав пройти"

        # 4-й — 429
        resp = await client.post("/api/print/jobs")
        assert resp.status_code == 429, f"Очікувався 429, отримано {resp.status_code}"


@pytest.mark.asyncio
async def test_429_response_format():
    """Тест 3: 429 відповідь має правильний формат і заголовок Retry-After."""
    app, _ = make_test_app("1/minute")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Forwarded-For": "3.3.3.3"},
    ) as client:
        await client.post("/api/print/jobs")  # перший — OK
        resp = await client.post("/api/print/jobs")  # другий — 429

        assert resp.status_code == 429
        body = resp.json()
        assert body["error"] == "RATE_LIMIT_EXCEEDED"
        assert "message" in body
        assert "retry_after" in body
        assert resp.headers.get("Retry-After") == "60"


@pytest.mark.asyncio
async def test_different_ips_have_independent_counters():
    """Тест 4: Різні IP — незалежні лічильники."""
    app, _ = make_test_app("2/minute")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # IP A — вичерпує ліміт
        for _ in range(2):
            r = await client.post(
                "/api/print/jobs", headers={"X-Forwarded-For": "10.0.0.1"}
            )
            assert r.status_code == 200

        r = await client.post(
            "/api/print/jobs", headers={"X-Forwarded-For": "10.0.0.1"}
        )
        assert r.status_code == 429

        # IP B — ще не вичерпав
        r = await client.post(
            "/api/print/jobs", headers={"X-Forwarded-For": "10.0.0.2"}
        )
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_x_forwarded_for_used_as_key():
    """Тест 5: X-Forwarded-For використовується як ключ rate limit."""
    app, _ = make_test_app("1/minute")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Запит з IP через X-Forwarded-For
        r1 = await client.post(
            "/api/print/jobs", headers={"X-Forwarded-For": "5.5.5.5"}
        )
        assert r1.status_code == 200

        # Другий запит з тим самим IP — 429
        r2 = await client.post(
            "/api/print/jobs", headers={"X-Forwarded-For": "5.5.5.5"}
        )
        assert r2.status_code == 429

        # З іншого IP — OK
        r3 = await client.post(
            "/api/print/jobs", headers={"X-Forwarded-For": "6.6.6.6"}
        )
        assert r3.status_code == 200


@pytest.mark.asyncio
async def test_x_real_ip_fallback():
    """Тест 6: X-Real-IP використовується якщо X-Forwarded-For відсутній."""
    app, _ = make_test_app("1/minute")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r1 = await client.post("/api/print/jobs", headers={"X-Real-IP": "7.7.7.7"})
        assert r1.status_code == 200

        r2 = await client.post("/api/print/jobs", headers={"X-Real-IP": "7.7.7.7"})
        assert r2.status_code == 429

        # Інший X-Real-IP — OK
        r3 = await client.post("/api/print/jobs", headers={"X-Real-IP": "8.8.8.8"})
        assert r3.status_code == 200


@pytest.mark.asyncio
async def test_forwarded_for_chain_uses_first_ip():
    """Тест 7: Ланцюжок X-Forwarded-For — береться перший (оригінальний клієнт)."""
    # "client, proxy1, proxy2" → "client"
    app, _ = make_test_app("1/minute")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r1 = await client.post(
            "/api/print/jobs",
            headers={"X-Forwarded-For": "9.9.9.9, 10.0.0.1, 172.16.0.1"},
        )
        assert r1.status_code == 200

        # Другий запит з тим самим оригінальним клієнтом — 429
        r2 = await client.post(
            "/api/print/jobs",
            headers={"X-Forwarded-For": "9.9.9.9, 10.0.0.2"},
        )
        assert r2.status_code == 429


@pytest.mark.asyncio
async def test_upload_endpoint_has_separate_limit():
    """Тест 8: /upload має окремий ліміт (3/minute у тесті)."""
    app, _ = make_test_app("10/minute")  # /jobs — 10, /upload — 3

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Forwarded-For": "11.11.11.11"},
    ) as client:
        # /jobs — ліміт 10, маємо простір
        for _ in range(5):
            r = await client.post("/api/print/jobs")
            assert r.status_code == 200

        # /upload — ліміт 3
        for _ in range(3):
            r = await client.post("/api/print/upload")
            assert r.status_code == 200

        # 4-й upload — 429
        r = await client.post("/api/print/upload")
        assert r.status_code == 429


# ── Unit-тести _get_real_ip ────────────────────────────────────────

def _make_request(headers: dict) -> Request:
    """Мінімальний Request з потрібними заголовками."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "query_string": b"",
        "client": ("127.0.0.1", 8000),
    }
    return Request(scope)


def test_get_real_ip_from_forwarded_for():
    """Unit: X-Forwarded-For → перший IP."""
    req = _make_request({"X-Forwarded-For": "1.2.3.4, 10.0.0.1"})
    assert _get_real_ip(req) == "1.2.3.4"


def test_get_real_ip_from_x_real_ip():
    """Unit: X-Real-IP якщо немає X-Forwarded-For."""
    req = _make_request({"X-Real-IP": "5.6.7.8"})
    assert _get_real_ip(req) == "5.6.7.8"


def test_get_real_ip_fallback_to_client():
    """Unit: Fallback на request.client.host."""
    req = _make_request({})
    assert _get_real_ip(req) == "127.0.0.1"


def test_forwarded_for_priority_over_real_ip():
    """Unit: X-Forwarded-For має пріоритет над X-Real-IP."""
    req = _make_request({
        "X-Forwarded-For": "1.1.1.1",
        "X-Real-IP": "2.2.2.2",
    })
    assert _get_real_ip(req) == "1.1.1.1"
