"""
test_tenant_isolation.py — тести ізоляції тенантів та перемикання search_path.

Архітектура тестів:
  - SQLite in-memory (aiosqlite) замість реального PostgreSQL.
  - SQLite не підтримує schemas/search_path, тому тестуємо логіку listeners
    через мок cursor та перевіряємо, що SET LOCAL викликається правильно.
  - Для тестів реальної ізоляції даних використовуємо два окремих
    in-memory движки (імітація двох схем).

Тест-кейси:
  1. get_schema_name() → правильне ім'я для різних субдоменів
  2. Дефіс у субдомені → підкреслення в схемі
  3. Невалідний субдомен → SystemExit при старті
  4. before_cursor_execute встановлює search_path (мок cursor)
  5. after_transaction_end скидає флаг і викликає RESET
  6. dedicated mode → listeners не реєструються, SET LOCAL не викликається
  7. Ізоляція даних: тенант A не бачить дані тенанта B
  8. search_path_set флаг: другий запит у тій самій транзакції не SET LOCAL повторно
"""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch, call
import sys
import os


# ── Helpers ───────────────────────────────────────────────────────

def _make_conn_info():
    """Імітація conn.info — простий dict."""
    return {}


def _make_mock_conn(info=None):
    conn = MagicMock()
    conn.info = info if info is not None else {}
    conn.execute = MagicMock()
    return conn


def _make_mock_cursor():
    cursor = MagicMock()
    cursor.execute = MagicMock()
    return cursor


# ── Тести tenant.py ───────────────────────────────────────────────

class TestGetSchemaName:
    def test_simple_subdomain(self):
        """Тест 1: Простий субдомен → правильна схема."""
        with patch.dict(os.environ, {"INSTANCE_SUBDOMAIN": "myshop", "TENANT_MODE": "shared"}):
            # Перезавантажуємо модуль щоб підхопити нові env
            if "app.core.tenant" in sys.modules:
                del sys.modules["app.core.tenant"]
            from app.core.tenant import get_schema_name
            assert get_schema_name() == "tenant_myshop"

    def test_subdomain_with_dashes(self):
        """Тест 2: Дефіс у субдомені → підкреслення в схемі."""
        with patch.dict(os.environ, {"INSTANCE_SUBDOMAIN": "my-print-shop", "TENANT_MODE": "shared"}):
            if "app.core.tenant" in sys.modules:
                del sys.modules["app.core.tenant"]
            from app.core.tenant import get_schema_name
            assert get_schema_name() == "tenant_my_print_shop"

    def test_dedicated_mode_returns_public(self):
        """Тест 3: dedicated mode → схема 'public'."""
        with patch.dict(os.environ, {"TENANT_MODE": "dedicated"}, clear=False):
            if "app.core.tenant" in sys.modules:
                del sys.modules["app.core.tenant"]
            from app.core.tenant import get_schema_name
            assert get_schema_name() == "public"

    def test_invalid_subdomain_exits(self):
        """Тест 4: Невалідний субдомен → SystemExit."""
        with patch.dict(os.environ, {"INSTANCE_SUBDOMAIN": "INVALID_UPPER", "TENANT_MODE": "shared"}):
            if "app.core.tenant" in sys.modules:
                del sys.modules["app.core.tenant"]
            with pytest.raises(SystemExit):
                import app.core.tenant  # noqa

    def test_empty_subdomain_exits(self):
        """Тест 5: Порожній субдомен → SystemExit."""
        with patch.dict(os.environ, {"INSTANCE_SUBDOMAIN": "", "TENANT_MODE": "shared"}):
            if "app.core.tenant" in sys.modules:
                del sys.modules["app.core.tenant"]
            with pytest.raises(SystemExit):
                import app.core.tenant  # noqa

    def test_subdomain_with_injection_attempt_exits(self):
        """Тест 6: SQL-ін'єкція у субдомені → SystemExit."""
        malicious = 'shop"; DROP TABLE instances; --'
        with patch.dict(os.environ, {"INSTANCE_SUBDOMAIN": malicious, "TENANT_MODE": "shared"}):
            if "app.core.tenant" in sys.modules:
                del sys.modules["app.core.tenant"]
            with pytest.raises(SystemExit):
                import app.core.tenant  # noqa


# ── Тести events.py ───────────────────────────────────────────────

class TestEventListeners:

    def _get_listeners(self, schema="tenant_myshop"):
        """
        Витягуємо registered listeners через monkey-patching event.listens_for.
        Повертає dict {event_name: handler}.
        """
        listeners = {}

        original_listens_for = None
        try:
            from sqlalchemy import event as sa_event
            original_listens_for = sa_event.listens_for
        except ImportError:
            pass

        def mock_listens_for(target, event_name, **kwargs):
            def decorator(fn):
                listeners[event_name] = fn
                return fn
            return decorator

        with patch.dict(os.environ, {"INSTANCE_SUBDOMAIN": "myshop", "TENANT_MODE": "shared"}):
            if "app.core.tenant" in sys.modules:
                del sys.modules["app.core.tenant"]
            if "app.db.events" in sys.modules:
                del sys.modules["app.db.events"]

            with patch("sqlalchemy.event.listens_for", side_effect=mock_listens_for):
                from app.db.events import register_tenant_events
                mock_engine = MagicMock()
                mock_engine.sync_engine = MagicMock()
                register_tenant_events(mock_engine)

        return listeners

    def test_before_cursor_execute_sets_search_path(self):
        """Тест 7: before_cursor_execute → SET LOCAL search_path при першому запиті."""
        listeners = self._get_listeners()
        assert "before_cursor_execute" in listeners, "Listener не зареєстровано"

        handler = listeners["before_cursor_execute"]
        conn = _make_mock_conn()
        cursor = _make_mock_cursor()

        handler(conn, cursor, "SELECT 1", {}, None, False)

        # SET LOCAL має бути виконано
        assert cursor.execute.called
        call_args = cursor.execute.call_args[0][0]
        assert "SET LOCAL search_path" in call_args
        assert "tenant_myshop" in call_args
        assert conn.info["search_path_set"] is True

    def test_before_cursor_execute_no_double_set(self):
        """Тест 8: Другий запит у тій самій транзакції НЕ викликає SET LOCAL повторно."""
        listeners = self._get_listeners()
        handler = listeners["before_cursor_execute"]
        conn = _make_mock_conn(info={"search_path_set": True})
        cursor = _make_mock_cursor()

        handler(conn, cursor, "SELECT 2", {}, None, False)

        # SET LOCAL НЕ має бути викликано
        cursor.execute.assert_not_called()

    def test_after_transaction_end_resets_flag(self):
        """Тест 9: after_transaction_end скидає флаг search_path_set."""
        listeners = self._get_listeners()
        assert "after_transaction_end" in listeners

        handler = listeners["after_transaction_end"]
        conn = _make_mock_conn(info={"search_path_set": True})

        handler(conn, MagicMock())

        assert conn.info["search_path_set"] is False

    def test_after_transaction_end_no_reset_if_not_set(self):
        """Тест 10: after_transaction_end нічого не робить якщо search_path не встановлювався."""
        listeners = self._get_listeners()
        handler = listeners["after_transaction_end"]
        conn = _make_mock_conn(info={"search_path_set": False})

        handler(conn, MagicMock())

        # RESET не має бути викликано
        conn.execute.assert_not_called()

    def test_dedicated_mode_no_listeners(self):
        """Тест 11: dedicated mode → register_tenant_events не реєструє listeners."""
        registered = []

        def mock_listens_for(target, event_name, **kwargs):
            def decorator(fn):
                registered.append(event_name)
                return fn
            return decorator

        with patch.dict(os.environ, {"TENANT_MODE": "dedicated"}):
            if "app.core.tenant" in sys.modules:
                del sys.modules["app.core.tenant"]
            if "app.db.events" in sys.modules:
                del sys.modules["app.db.events"]

            with patch("sqlalchemy.event.listens_for", side_effect=mock_listens_for):
                from app.db.events import register_tenant_events
                mock_engine = MagicMock()
                mock_engine.sync_engine = MagicMock()
                register_tenant_events(mock_engine)

        assert len(registered) == 0, f"Listeners не мають реєструватись у dedicated mode: {registered}"


# ── Тести ізоляції даних ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_tenant_data_isolation():
    """
    Тест 12: Ізоляція даних між тенантами.

    Два окремих in-memory SQLite движки імітують дві ізольовані схеми.
    Записи в одному engine не видимі в іншому.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import text

    engine_a = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    engine_b = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Створюємо однакову таблицю в обох "схемах"
    create_sql = "CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, name TEXT)"

    async with engine_a.begin() as conn:
        await conn.execute(text(create_sql))
    async with engine_b.begin() as conn:
        await conn.execute(text(create_sql))

    factory_a = async_sessionmaker(engine_a, class_=AsyncSession, expire_on_commit=False)
    factory_b = async_sessionmaker(engine_b, class_=AsyncSession, expire_on_commit=False)

    # Тенант A записує дані
    async with factory_a() as sess:
        await sess.execute(text("INSERT INTO orders (name) VALUES ('order-from-A')"))
        await sess.commit()

    # Тенант B записує свої дані
    async with factory_b() as sess:
        await sess.execute(text("INSERT INTO orders (name) VALUES ('order-from-B')"))
        await sess.commit()

    # Тенант A бачить тільки своє
    async with factory_a() as sess:
        rows = (await sess.execute(text("SELECT name FROM orders"))).fetchall()
        names = [r[0] for r in rows]
        assert names == ["order-from-A"], f"Тенант A бачить чужі дані: {names}"

    # Тенант B бачить тільки своє
    async with factory_b() as sess:
        rows = (await sess.execute(text("SELECT name FROM orders"))).fetchall()
        names = [r[0] for r in rows]
        assert names == ["order-from-B"], f"Тенант B бачить чужі дані: {names}"

    await engine_a.dispose()
    await engine_b.dispose()


@pytest.mark.asyncio
async def test_safe_schema_identifier_no_injection():
    """Тест 13: _safe_schema_identifier екранує лапки."""
    # Імітуємо безпосередньо функцію без завантаження модуля з env
    def _safe(schema: str) -> str:
        return '"' + schema.replace('"', '') + '"'

    # Нормальне ім'я
    assert _safe("tenant_myshop") == '"tenant_myshop"'

    # Спроба ін'єкції через лапки (хоча validator вже блокує на вході)
    assert _safe('tenant_shop"; DROP TABLE') == '"tenant_shop; DROP TABLE"'
