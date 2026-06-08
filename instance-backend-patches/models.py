"""
models.py — SQLAlchemy 2.0 моделі PrintJob та PrintedFile.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, BigInteger, DateTime, ForeignKey, func, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PrintJob(Base):
    """
    Замовлення на друк — може містити кілька файлів.
    Статуси: draft | processing | ready_to_print | printed | failed
    """
    __tablename__ = "print_jobs"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # Параметри друку (заповнюються клієнтом)
    copies: Mapped[int] = mapped_column(Integer, default=1)
    duplex: Mapped[bool] = mapped_column(Boolean, default=False)       # двосторонній
    color_mode: Mapped[str] = mapped_column(String, default="bw")      # bw | color
    page_range: Mapped[str | None] = mapped_column(String, nullable=True)  # "1-5, 8"
    orientation: Mapped[str] = mapped_column(String, default="portrait")   # portrait | landscape
    photo_size: Mapped[str | None] = mapped_column(String, nullable=True)  # "10×15" etc

    status: Mapped[str] = mapped_column(String, default="draft", index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    files: Mapped[list["PrintedFile"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PrintJob id={self.id!r} user={self.user_id} status={self.status!r}>"


class PrintedFile(Base):
    """
    Файл прив'язаний до замовлення.
    Статуси: uploaded | processing | ready_to_print | failed
    """
    __tablename__ = "printed_files"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        String, ForeignKey("print_jobs.id", ondelete="CASCADE"), index=True
    )

    # Імена та шляхи
    original_name: Mapped[str] = mapped_column(String)       # ім'я від клієнта
    safe_name: Mapped[str] = mapped_column(String)           # безпечне ім'я на диску
    file_path: Mapped[str] = mapped_column(String)           # абсолютний шлях
    pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)  # після конвертації

    # Метадані файлу
    mime_type: Mapped[str] = mapped_column(String)
    file_size: Mapped[int] = mapped_column(BigInteger)       # байти

    # Метадані після аналізу
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_color: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    paper_format: Mapped[str | None] = mapped_column(String, nullable=True)  # A4 | A3

    # Статус обробки файлу
    status: Mapped[str] = mapped_column(String, default="uploaded", index=True)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    job: Mapped["PrintJob"] = relationship(back_populates="files")

    def __repr__(self) -> str:
        return f"<PrintedFile id={self.id!r} name={self.original_name!r} status={self.status!r}>"
