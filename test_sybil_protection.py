"""
test_sybil_protection.py — тести Sybil-захисту для POST /api/instances/create.

База: SQLite in-memory (aiosqlite) — не потребує реального PostgreSQL.
Мокуємо: encrypt_secret, verify_manager_access, redis_pool.

Тест-кейси:
  1. Новий користувач, Free — 202 ✓
  2. Той самий Free-користувач, ще один Free — 409 ✗
  3. Free-користувач, Start — 202 ✓ (bypass)
  4. Free-користувач, Business — 202 ✓ (bypass)
  5. Free-користувач, Demo — 202 ✓ (demo не рахується)
  6. Pydantic: owner_telegram_id = 0 — 422 ✗
  7. Pydantic: owner_telegram_id відсутній — 422 ✗
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from fastapi import FastAPI

# ── Патчимо залежності ДО імпорту app-модулів ─────────────────────
# security.py потребує FERNET_KEY — мокуємо на рівні модуля
import sys
from unittest.mock import MagicMock

# Мок security
security_mock = MagicMock()
security_mock.encrypt_secret = lambda s: f"enc:{s}"
security_mock.decrypt_secret = lambda s: s.replace("enc:", "")
security_mock.verify_manager_access = lambda: None
sys.modules["app.security"] = security_mock

# Мок ws_manager
ws_mock = MagicMock()
ws_mock.ws_manager = MagicMock()
sys.modules["app.ws_manager"] = ws_mock

from app.models import Base, InstanceRegistry
from app.orchestrator import router, public_router, _check_sybil


# ── Фікстури ──────────────────────────────────────────────────────

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine):
    """
    Тестовий FastAPI-клієнт з підміненою БД і замоканим redis.
    """
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_db():
        async with factory() as session:
            yield session

    redis_mock = AsyncMock()
    redis_mock.enqueue_job = AsyncMock()

    async def override_redis():
        return redis_mock

    app = FastAPI()
    app.include_router(router)
    app.include_router(public_router)

    from app.manager_db import get_manager_db, get_redis_pool
    app.dependency_overrides[get_manager_db] = override_db
    app.dependency_overrides[get_redis_pool] = override_redis

    # verify_manager_access замінений на no-op через sys.modules мок вище,
    # але на всяк випадок перевизначаємо і через overrides
    from app.security import verify_manager_access
    app.dependency_overrides[verify_manager_access] = lambda: None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def _payload(**kwargs) -> dict:
    """Базовий payload для створення інстансу."""
    base = {
        "subdomain": "test-shop-01",
        "tg_bot_token": "1234567890:AABBCCDDEEFFaabbccddeeff123456789",
        "owner_telegram_id": 123456789,
        "plan_tier": "free",
        "is_demo": False,
    }
    base.update(kwargs)
    return base


# ── Тести ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_new_free_user_creates_instance(client):
    """Тест 1: Новий користувач Free — успішне створення (202)."""
    resp = await client.post("/api/instances/create", json=_payload())
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["status"] == "accepted"
    assert "instance_id" in data


@pytest.mark.asyncio
async def test_second_free_instance_blocked(client):
    """Тест 2: Той самий Telegram ID вже має Free — 409."""
    # Перший інстанс
    r1 = await client.post(
        "/api/instances/create",
        json=_payload(subdomain="shop-first"),
    )
    assert r1.status_code == 202, r1.text

    # Спроба другого Free
    r2 = await client.post(
        "/api/instances/create",
        json=_payload(subdomain="shop-second"),
    )
    assert r2.status_code == 409, r2.text
    assert "free instance is already associated" in r2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_free_user_can_create_start_instance(client):
    """Тест 3: Є Free — можна створити Start (paid bypass)."""
    await client.post("/api/instances/create", json=_payload(subdomain="shop-free"))

    r = await client.post(
        "/api/instances/create",
        json=_payload(
            subdomain="shop-start",
            plan_tier="start",
            owner_telegram_id=123456789,
        ),
    )
    assert r.status_code == 202, r.text


@pytest.mark.asyncio
async def test_free_user_can_create_business_instance(client):
    """Тест 4: Є Free — можна створити Business."""
    await client.post("/api/instances/create", json=_payload(subdomain="shop-free2"))

    r = await client.post(
        "/api/instances/create",
        json=_payload(
            subdomain="shop-business",
            plan_tier="business",
            owner_telegram_id=123456789,
        ),
    )
    assert r.status_code == 202, r.text


@pytest.mark.asyncio
async def test_free_user_can_create_demo_instance(client):
    """Тест 5: Є Free — demo не рахується, створення дозволено."""
    await client.post("/api/instances/create", json=_payload(subdomain="shop-free3"))

    r = await client.post(
        "/api/instances/create",
        json=_payload(
            subdomain="shop-demo",
            plan_tier="free",
            is_demo=True,
            owner_telegram_id=123456789,
        ),
    )
    assert r.status_code == 202, r.text


@pytest.mark.asyncio
async def test_invalid_telegram_id_zero(client):
    """Тест 6: owner_telegram_id = 0 — Pydantic відхиляє (422)."""
    r = await client.post(
        "/api/instances/create",
        json=_payload(owner_telegram_id=0),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_missing_telegram_id(client):
    """Тест 7: owner_telegram_id відсутній — Pydantic відхиляє (422)."""
    payload = _payload()
    del payload["owner_telegram_id"]
    r = await client.post("/api/instances/create", json=payload)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_different_users_can_each_have_free(client):
    """Бонус: різні Telegram ID — кожен може мати свій Free."""
    r1 = await client.post(
        "/api/instances/create",
        json=_payload(subdomain="shop-user1", owner_telegram_id=111111),
    )
    r2 = await client.post(
        "/api/instances/create",
        json=_payload(subdomain="shop-user2", owner_telegram_id=222222),
    )
    assert r1.status_code == 202
    assert r2.status_code == 202


@pytest.mark.asyncio
async def test_sybil_check_unit(db_session):
    """Unit-тест _check_sybil напряму: перевіряє логіку без HTTP."""
    from fastapi import HTTPException

    # Немає інстансів — не кидає
    await _check_sybil(db_session, owner_telegram_id=999, plan_tier="free", is_demo=False)

    # Додаємо Free-інстанс
    inst = InstanceRegistry(
        subdomain="existing-shop",
        encrypted_tg_bot_token="enc:token",
        encrypted_db_password="enc:pass",
        owner_telegram_id=999,
        plan_tier="free",
        is_demo=False,
    )
    db_session.add(inst)
    await db_session.commit()

    # Тепер має кинути 409
    with pytest.raises(HTTPException) as exc_info:
        await _check_sybil(
            db_session, owner_telegram_id=999, plan_tier="free", is_demo=False
        )
    assert exc_info.value.status_code == 409

    # Paid — не кидає
    await _check_sybil(
        db_session, owner_telegram_id=999, plan_tier="start", is_demo=False
    )

    # Demo — не кидає
    await _check_sybil(
        db_session, owner_telegram_id=999, plan_tier="free", is_demo=True
    )
