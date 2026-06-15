"""
models.py — SQLAlchemy 2.0 модель реєстру інстансів.

Зміни відносно попередньої версії:
  - owner_telegram_id: BigInteger — Telegram ID власника (для Sybil-захисту)
  - plan_tier: str — тарифний план ('free' | 'start' | 'business')
  - is_demo: bool — демо-інстанс не рахується у Free-ліміт

Нотатки щодо updated_at:
  - server_default=func.now() → PostgreSQL виставляє при INSERT
  - onupdate=func.now() → ORM додає при UPDATE (клієнтська сторона)
  - Надійне серверне оновлення забезпечується PostgreSQL-тригером
    у міграції alembic/versions/xxxx_add_updated_at_trigger.py
"""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, BigInteger, Boolean, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class InstanceRegistry(Base):
    __tablename__ = "instances"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    subdomain: Mapped[str] = mapped_column(String, unique=True, index=True)

    # Секрети зберігаються ТІЛЬКИ у зашифрованому вигляді (Fernet)
    encrypted_tg_bot_token: Mapped[str] = mapped_column(String)
    encrypted_db_password: Mapped[str] = mapped_column(String)

    # Статуси: provisioning | active | failed | stopped | maintenance
    status: Mapped[str] = mapped_column(String, default="provisioning")

    # ── Тариф і власник ───────────────────────────────────────────
    # Telegram ID власника; використовується для Sybil-захисту Free-тарифу.
    # Nullable: NULL означає "системний" або legacy-інстанс без власника.
    owner_telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True
    )
    # Тарифний план: 'free' | 'start' | 'business'
    plan_tier: Mapped[str] = mapped_column(String, default="free")
    # Демо-інстанс: не рахується у ліміт Free-тарифу
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Секрет оператора (зашифрований Fernet)
    encrypted_operator_secret: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    # Зберігає повний traceback при статусі "failed"
    error_log: Mapped[str | None] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<InstanceRegistry subdomain={self.subdomain!r} "
            f"status={self.status!r} plan={self.plan_tier!r}>"
        )
