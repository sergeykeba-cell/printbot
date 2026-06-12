"""
test_plan_enforcement.py — unit-тести для PlanEnforcementMiddleware.
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.middleware.plan_enforcement import PlanEnforcementMiddleware
from app.core.cache import TTLCache


def make_app(plan_tier="free", max_orders=30, bonus=0):
    app = FastAPI()
    app.add_middleware(PlanEnforcementMiddleware)

    config = {
        "instance_id": "test-id",
        "subdomain": "test-shop",
        "plan_tier": plan_tier,
        "max_orders_per_month": max_orders,
        "bonus_orders": bonus,
    }

    @app.post("/api/v1/orders")
    async def create_order():
        return {"status": "created"}

    @app.get("/api/v1/internal/config")
    async def get_config():
        return config

    return app, config


@pytest.mark.asyncio
async def test_free_under_limit():
    """Тест 1: Free-тариф, ліміт не вичерпано — запит проходить (200)."""
    app, config = make_app(plan_tier="free", max_orders=30)

    with patch("app.middleware.plan_enforcement._get_config", return_value=config), \
         patch("app.middleware.plan_enforcement._count_month_orders", return_value=5):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/orders")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_free_limit_reached():
    """Тест 2: Free-тариф, ліміт вичерпано — повертається 402."""
    app, config = make_app(plan_tier="free", max_orders=30)

    with patch("app.middleware.plan_enforcement._get_config", return_value=config), \
         patch("app.middleware.plan_enforcement._count_month_orders", return_value=30):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/orders")
        assert resp.status_code == 402
        assert resp.json()["error"] == "LIMIT_REACHED"


@pytest.mark.asyncio
async def test_non_free_always_passes():
    """Тест 3: Не-Free тариф — завжди проходить незалежно від кількості."""
    app, config = make_app(plan_tier="pro", max_orders=30)
    config["plan_tier"] = "pro"

    with patch("app.middleware.plan_enforcement._get_config", return_value=config), \
         patch("app.middleware.plan_enforcement._count_month_orders", return_value=999):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/orders")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_cache_used_on_second_request():
    """Тест 4: Кеш використовується — конфігурація завантажується лише раз."""
    app, config = make_app(plan_tier="free", max_orders=30)

    fetch_mock = AsyncMock(return_value=config)
    with patch("app.middleware.plan_enforcement._fetch_config", fetch_mock), \
         patch("app.middleware.plan_enforcement._count_month_orders", return_value=0):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/orders")
            await client.post("/api/v1/orders")
        assert fetch_mock.call_count <= 1


@pytest.mark.asyncio
async def test_stale_cache_on_config_failure():
    """Тест 5: При відмові зовнішнього API використовуються застарілі дані."""
    cache = TTLCache(ttl=300)
    stale_config = {
        "instance_id": "test-id",
        "subdomain": "test-shop",
        "plan_tier": "free",
        "max_orders_per_month": 30,
        "bonus_orders": 0,
    }
    await cache.set("default", stale_config)
    # Симулюємо прострочення
    cache._store["default"] = (stale_config, 0)

    with patch("app.middleware.plan_enforcement.instance_config_cache", cache), \
         patch("app.middleware.plan_enforcement._fetch_config", return_value=None), \
         patch("app.middleware.plan_enforcement._count_month_orders", return_value=5):
        app, _ = make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/orders")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_bonus_orders_extend_limit():
    """Тест 6: bonus_orders розширює ліміт (30 + 10 = 40)."""
    app, config = make_app(plan_tier="free", max_orders=30, bonus=10)

    with patch("app.middleware.plan_enforcement._get_config", return_value=config), \
         patch("app.middleware.plan_enforcement._count_month_orders", return_value=35):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/orders")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_config_unavailable_returns_503():
    """Тест 7: Конфіг недоступний і кешу немає — 503."""
    app, _ = make_app()

    with patch("app.middleware.plan_enforcement._get_config", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/orders")
        assert resp.status_code == 503
        assert resp.json()["error"] == "SERVICE_UNAVAILABLE"
