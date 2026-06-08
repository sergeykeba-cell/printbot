"""
models.py — SQLAlchemy 2.0 модель реєстру інстансів.

Нотатки щодо updated_at:
- server_default=func.now() → PostgreSQL виставляє при INSERT
- onupdate=func.now() → ORM додає при UPDATE (клієнтська сторона)
- Надійне серверне оновлення забезпечується PostgreSQL-тригером
  у міграції alembic/versions/xxxx_add_updated_at_trigger.py
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func
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

    # Статуси: provisioning | active | failed | stopped
    status: Mapped[str] = mapped_column(String, default="provisioning")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),  # ORM-рівень; тригер у БД — головний
    )

    # Зберігає повний traceback при статусі "failed"
    error_log: Mapped[str | None] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<InstanceRegistry subdomain={self.subdomain!r} status={self.status!r}>"
