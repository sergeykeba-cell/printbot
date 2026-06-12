"""
Alembic migration: додаємо білінгові поля до таблиці instances.

Нові поля:
  - plan         : тарифний план (free / basic / pro), дефолт 'free'
  - billing_suspended : чи призупинено інстанс через несплату
  - trial_ends_at     : дата закінчення тріалу (NULL = немає тріалу)
  - monthly_fee       : щомісячна вартість плану в UAH

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "instances",
        sa.Column("plan", sa.String(), nullable=False, server_default="free"),
    )
    op.add_column(
        "instances",
        sa.Column(
            "billing_suspended",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "instances",
        sa.Column(
            "trial_ends_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "instances",
        sa.Column(
            "monthly_fee",
            sa.Numeric(precision=10, scale=2),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("instances", "monthly_fee")
    op.drop_column("instances", "trial_ends_at")
    op.drop_column("instances", "billing_suspended")
    op.drop_column("instances", "plan")
