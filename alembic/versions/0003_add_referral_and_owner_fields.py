"""
Alembic migration: додаємо 8 бізнес-полів до таблиці instances.

Zero-downtime стратегія (3 фази):
  Phase 1: DDL — додаємо nullable колонки (без блокування)
  Phase 2: DML — backfill існуючих рядків через raw SQL
  Phase 3: DDL — накладаємо NOT NULL + UNIQUE constraints

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ── Phase 1: DDL — додаємо всі колонки як nullable ────────────

    # owner_telegram_id — спочатку nullable для backfill
    op.add_column(
        "instances",
        sa.Column("owner_telegram_id", sa.BigInteger(), nullable=True),
    )

    # referral_code — спочатку nullable для backfill
    op.add_column(
        "instances",
        sa.Column("referral_code", sa.String(16), nullable=True),
    )

    # Решта колонок — одразу з фінальними constraints
    op.add_column(
        "instances",
        sa.Column("referred_by", sa.String(16), nullable=True),
    )
    op.add_column(
        "instances",
        sa.Column(
            "bonus_orders",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "instances",
        sa.Column(
            "bonus_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "instances",
        sa.Column(
            "first_order_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "instances",
        sa.Column(
            "language",
            sa.String(5),
            nullable=False,
            server_default="uk",
        ),
    )
    op.add_column(
        "instances",
        sa.Column("tax_country_code", sa.String(2), nullable=True),
    )

    # ── Phase 2: DML — backfill існуючих рядків ───────────────────

    # referral_code: детермінований MD5 хеш subdomain+id, 12 символів upper
    op.execute("""
        UPDATE instances
        SET referral_code = UPPER(SUBSTRING(MD5(subdomain || id::text) FROM 1 FOR 12))
        WHERE referral_code IS NULL;
    """)

    # owner_telegram_id: для legacy рядків — хеш id щоб уникнути NULL
    # (реальне значення адмін оновить вручну або через API)
    op.execute("""
        UPDATE instances
        SET owner_telegram_id = ABS(('x' || SUBSTRING(MD5(id::text) FROM 1 FOR 15))::bit(60)::bigint)
        WHERE owner_telegram_id IS NULL;
    """)

    # ── Phase 3: DDL — накладаємо фінальні constraints ────────────

    # owner_telegram_id → NOT NULL + index
    op.alter_column("instances", "owner_telegram_id", nullable=False)
    op.create_index(
        "ix_instances_owner_telegram_id",
        "instances",
        ["owner_telegram_id"],
    )

    # referral_code → NOT NULL + UNIQUE + index
    op.alter_column("instances", "referral_code", nullable=False)
    op.create_unique_constraint(
        "uq_instances_referral_code",
        "instances",
        ["referral_code"],
    )
    op.create_index(
        "ix_instances_referral_code",
        "instances",
        ["referral_code"],
    )

    # referred_by → index (nullable, без unique)
    op.create_index(
        "ix_instances_referred_by",
        "instances",
        ["referred_by"],
    )


def downgrade() -> None:
    op.drop_index("ix_instances_referred_by", table_name="instances")
    op.drop_index("ix_instances_referral_code", table_name="instances")
    op.drop_constraint("uq_instances_referral_code", "instances", type_="unique")
    op.drop_index("ix_instances_owner_telegram_id", table_name="instances")

    op.drop_column("instances", "tax_country_code")
    op.drop_column("instances", "language")
    op.drop_column("instances", "first_order_at")
    op.drop_column("instances", "bonus_expires_at")
    op.drop_column("instances", "bonus_orders")
    op.drop_column("instances", "referred_by")
    op.drop_column("instances", "referral_code")
    op.drop_column("instances", "owner_telegram_id")
