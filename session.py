"""
database.py — Асинхронна сесія SQLAlchemy та Redis пул для бота.

Зміни відносно попередньої версії:
  - Після створення engine викликається register_tenant_events(engine),
    яка підключає before_cursor_execute / after_transaction_end listeners
    для автоматичного перемикання search_path у shared-режимі.
  - У dedicated-режимі (TENANT_MODE=dedicated) listeners не реєструються,
    жодних змін у поведінці немає.
"""
import os
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.models import Base
from app.db.events import register_tenant_events

logger = logging.getLogger("database")

DATABASE_URL: str = os.environ["DATABASE_URL"]

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# ── Реєструємо tenant search_path listeners ────────────────────────
# Виконується один раз при імпорті модуля.
# У shared-режимі підключає before_cursor_execute + after_transaction_end.
# У dedicated-режимі — no-op.
register_tenant_events(engine)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# ── Redis пул ─────────────────────────────────────────────────────

_redis_pool = None


async def init_redis() -> None:
    global _redis_pool
    from arq.connections import create_pool, RedisSettings
    _redis_pool = await create_pool(RedisSettings.from_dsn(os.environ["REDIS_URL"]))


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


async def get_redis_pool():
    if _redis_pool is None:
        raise RuntimeError("Redis pool не ініціалізовано.")
    yield _redis_pool
