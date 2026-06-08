"""
alembic/env.py — Налаштування середовища Alembic для асинхронного движка.

Підтримує:
  - asyncpg / postgresql+asyncpg
  - Автоімпорт моделей через app.models.Base
  - Змінна MANAGER_DATABASE_URL з .env (через python-dotenv або os.environ)

Запуск:
  alembic upgrade head
  alembic downgrade -1
  alembic revision --autogenerate -m "description"
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Імпорт моделей ────────────────────────────────────────────────
# ВАЖЛИВО: Base.metadata має містити всі таблиці для autogenerate.
# Якщо додаєш нові моделі — імпортуй їх тут.
from app.models import Base  # noqa: F401  ← підтягує InstanceRegistry

# ── Alembic Config ────────────────────────────────────────────────
config = context.config

# Логування з alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata для autogenerate (порівнює поточний стан БД зі схемою моделей)
target_metadata = Base.metadata


# ── Підстановка DATABASE_URL з env ───────────────────────────────
def get_url() -> str:
    """
    Читає URL з змінної середовища.
    Пріоритет: os.environ > alembic.ini [sqlalchemy.url].
    Падає з KeyError якщо змінна не виставлена — навмисно,
    щоб не запускати міграції з порожнім URL.
    """
    url = os.environ.get("MANAGER_DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError(
            "MANAGER_DATABASE_URL не виставлено. "
            "Встанови змінну середовища або sqlalchemy.url в alembic.ini"
        )
    return url


# ── Offline mode (генерація SQL без підключення до БД) ───────────
def run_migrations_offline() -> None:
    """
    Генерує SQL-скрипт без реального підключення.
    Корисно для перегляду міграцій перед застосуванням.
    Запуск: alembic upgrade head --sql
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,           # Відстежувати зміни типів колонок
        compare_server_default=True, # Відстежувати зміни server_default
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (реальне підключення через asyncpg) ───────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Асинхронний engine для asyncpg.
    NullPool — правильний вибір для міграцій (короткоживучий процес,
    не потребує пулу з'єднань).
    """
    url = get_url()

    # Замінюємо синхронний драйвер на asyncpg якщо потрібно
    # (підтримка як postgresql:// так і postgresql+asyncpg://)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    connectable = async_engine_from_config(
        {"sqlalchemy.url": url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Точка входу для online-режиму."""
    asyncio.run(run_async_migrations())


# ── Вибір режиму ─────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
