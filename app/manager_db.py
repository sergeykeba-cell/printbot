"""
manager_db.py — Асинхронна сесія SQLAlchemy для FastAPI та ARQ воркера.

Використання:
- FastAPI ендпоінти: Depends(get_manager_db), Depends(get_redis_pool)
- ARQ worker: async with AsyncSessionLocal() as db: ...
"""

import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.models import Base

# Падаємо при старті якщо змінна не виставлена
DATABASE_URL: str = os.environ["MANAGER_DATABASE_URL"]

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Глобальний ARQ пул — ініціалізується в lifespan (main.py)
_redis_pool = None


async def init_db() -> None:
    """Створити таблиці якщо не існують (dev/test). В prod — Alembic."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def init_redis() -> None:
    """Створити глобальний ARQ пул. Викликається один раз при старті."""
    global _redis_pool
    from arq.connections import create_pool, RedisSettings
    _redis_pool = await create_pool(RedisSettings.from_dsn(os.environ["REDIS_URL"]))


async def close_redis() -> None:
    """Закрити пул при зупинці застосунку."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


async def get_manager_db():
    """FastAPI Depends: надає сесію на час запиту."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_redis_pool():
    """FastAPI Depends: повертає глобальний пул (не створює новий)."""
    if _redis_pool is None:
        raise RuntimeError("Redis pool не ініціалізовано. Перевірте lifespan.")
    yield _redis_pool
