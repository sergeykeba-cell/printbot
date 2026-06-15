"""
events.py — SQLAlchemy event listeners для безпечного перемикання search_path.

Стратегія: Варіант А (before_cursor_execute + after_transaction_end)
  — рекомендовано для PgBouncer transaction pooling.

Як це працює:
  1. before_cursor_execute:
     Перед КОЖНИМ SQL-запитом перевіряємо мітку conn.info["search_path_set"].
     Якщо ще не встановлено в поточній транзакції — виконуємо
     SET LOCAL search_path TO <schema>, public
     SET LOCAL діє лише до кінця транзакції → безпечно для пулу.

  2. after_transaction_end:
     Після commit/rollback скидаємо мітку conn.info["search_path_set"].
     Це дозволяє наступній транзакції (можливо для іншого тенанта)
     знову встановити свій search_path.

Чому SET LOCAL, а не SET:
  - SET змінює search_path на рівні сесії — небезпечно для пулу,
    з'єднання поверталось би з "забрудненим" станом.
  - SET LOCAL скидається автоматично при кінці транзакції.
  - RESET search_path після транзакції — додатковий страховий рівень.

Чому не after_begin:
  - asyncpg не гарантує виклик after_begin для кожної операції
    при autocommit або при implicit begin.
  - before_cursor_execute спрацьовує надійно для будь-якого запиту.

Безпека від SQL-ін'єкцій:
  - Ім'я схеми validated at startup в tenant.py (regex).
  - Тут додатково екрануємо через подвійні лапки і replace('"', '').
    Це надлишкова перевірка — валідний subdomain не може містити лапки,
    але захищає від future bugs.
"""
import logging
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.tenant import get_schema_name, is_shared

logger = logging.getLogger("tenant.events")

# Ключ у conn.info для відстеження стану в поточній транзакції
_SEARCH_PATH_KEY = "search_path_set"


def _safe_schema_identifier(schema: str) -> str:
    """
    Повертає безпечний SQL-ідентифікатор схеми в подвійних лапках.
    Видаляє будь-які подвійні лапки з імені (надлишковий захист).
    """
    return '"' + schema.replace('"', '') + '"'


def register_tenant_events(engine: AsyncEngine) -> None:
    """
    Реєструє event listeners для schema-switching на переданому engine.
    Якщо TENANT_MODE=dedicated — нічого не робить.

    Args:
        engine: AsyncEngine, до якого прив'язуються listeners.
    """
    if not is_shared():
        logger.debug("[tenant.events] TENANT_MODE=dedicated — listeners не реєструються.")
        return

    schema = get_schema_name()
    safe_schema = _safe_schema_identifier(schema)
    # SET LOCAL search_path TO "tenant_my_shop", public
    # "public" без лапок — стандартна схема PostgreSQL
    set_search_path_sql = f'SET LOCAL search_path TO {safe_schema}, public'
    reset_search_path_sql = "RESET search_path"

    # SQLAlchemy async engine використовує sync_engine всередині
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """
        Встановлює search_path перед першим запитом у транзакції.

        conn.info — dict, прив'язаний до конкретного з'єднання (не до сесії),
        живе весь час, поки з'єднання у пулі. Використовуємо його як
        per-connection флаг.

        Пропускаємо рекурсію: якщо виконуємо сам SET LOCAL — не йдемо знову.
        """
        if conn.info.get(_SEARCH_PATH_KEY):
            return  # Вже встановлено в цій транзакції

        # Встановлюємо флаг ДО виконання, щоб уникнути нескінченної рекурсії
        conn.info[_SEARCH_PATH_KEY] = True
        try:
            cursor.execute(set_search_path_sql)
            logger.debug(f"[tenant.events] search_path → {schema}")
        except Exception as e:
            # Не блокуємо запит при помилці SET LOCAL,
            # але логуємо — це критично для діагностики
            conn.info[_SEARCH_PATH_KEY] = False
            logger.error(f"[tenant.events] Не вдалося встановити search_path: {e}")

    @event.listens_for(sync_engine, "after_transaction_end")
    def _after_transaction_end(conn, transaction):
        """
        Скидає мітку після завершення транзакції (commit або rollback).

        Це дозволяє наступній транзакції знову викликати SET LOCAL.
        RESET search_path виконується явно як страховий захід —
        навіть якщо SET LOCAL вже скинув значення автоматично.
        """
        if not conn.info.get(_SEARCH_PATH_KEY):
            return  # Нічого не встановлювали — нічого скидати

        conn.info[_SEARCH_PATH_KEY] = False
        try:
            conn.execute(text(reset_search_path_sql))
            logger.debug("[tenant.events] search_path → RESET")
        except Exception as e:
            # З'єднання може бути вже закрите або в поганому стані
            logger.warning(f"[tenant.events] Не вдалося скинути search_path: {e}")

    logger.info(
        f"[tenant.events] Зареєстровано listeners: "
        f"before_cursor_execute + after_transaction_end → schema={schema!r}"
    )
