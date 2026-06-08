"""
Alembic migration: PostgreSQL тригер для автоматичного оновлення updated_at.

Чому тригер, а не server_onupdate:
  - server_onupdate в SQLAlchemy — лише підказка для рефлекції, не DDL
  - PostgreSQL не має синтаксису ON UPDATE для колонок (на відміну від MySQL)
  - Тригер гарантує оновлення при БУДЬ-ЯКОМУ UPDATE: ORM, raw SQL, bulk update

Revision ID: 0001
"""

from alembic import op


def upgrade() -> None:
    # Функція тригера в public схемі (explicit)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Прив'язуємо тригер до таблиці instances
    op.execute("""
        CREATE TRIGGER trg_instances_updated_at
        BEFORE UPDATE ON instances
        FOR EACH ROW
        EXECUTE FUNCTION public.update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_instances_updated_at ON instances;")
    op.execute("DROP FUNCTION IF EXISTS public.update_updated_at_column();")
