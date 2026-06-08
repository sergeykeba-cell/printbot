"""
schemas.py — Pydantic v2 схеми валідації.
"""

import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


# ── Білий список дозволених MIME-типів ────────────────────────────
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",                                                    # .doc
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.oasis.opendocument.text",                              # .odt
    "image/png",
    "image/jpeg",
}

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".odt", ".png", ".jpg", ".jpeg"}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


# ── Валідація діапазону сторінок ───────────────────────────────────
_PAGE_RANGE_RE = re.compile(r"^(\d+(-\d+)?)(,\s*\d+(-\d+)?)*$")


def validate_page_range(v: str) -> str:
    """Валідує рядок типу '1-5, 8, 10-12'."""
    v = v.strip()
    if not _PAGE_RANGE_RE.match(v):
        raise ValueError(
            "Невірний формат діапазону сторінок. "
            "Використовуйте формат: '1-5, 8, 10-12'"
        )
    # Перевіряємо що кінець діапазону більший за початок
    for part in v.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            if int(start) >= int(end):
                raise ValueError(
                    f"Невірний діапазон '{part}': початок має бути меншим за кінець."
                )
            if int(start) < 1:
                raise ValueError("Номери сторінок мають бути >= 1.")
    return v


# ── Схема параметрів друку ─────────────────────────────────────────
class PrintConfigSchema(BaseModel):
    """Параметри конфігурації замовлення на друк."""

    copies: int = Field(default=1, ge=1, le=999, description="Кількість копій (1–999)")
    duplex: bool = Field(default=False, description="Двосторонній друк")
    color_mode: str = Field(default="bw", description="Режим кольору: 'bw' або 'color'")
    page_range: Optional[str] = Field(
        default=None,
        description="Діапазон сторінок: '1-5, 8' або None для всіх сторінок",
    )

    orientation: str = Field(default="portrait", description="Орієнтація: portrait | landscape")
    photo_size: Optional[str] = Field(default=None, description="Розмір фото: 10×15 etc")

    @field_validator("color_mode")
    @classmethod
    def validate_color_mode(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("bw", "color"):
            raise ValueError("color_mode має бути 'bw' або 'color'.")
        return v

    @field_validator("page_range")
    @classmethod
    def validate_page_range_field(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        return validate_page_range(v)


# ── Схема відповіді після завантаження файлу ──────────────────────
class FileUploadResponse(BaseModel):
    """Відповідь після успішного завантаження файлу."""
    file_id: str
    job_id: str
    original_name: str
    file_size: int
    mime_type: str
    status: str
    message: str


# ── Схема відповіді файлу (публічна) ──────────────────────────────
class PrintedFileResponse(BaseModel):
    """Публічне представлення файлу — без системних шляхів."""
    id: str
    original_name: str
    mime_type: str
    file_size: int
    page_count: Optional[int]
    is_color: Optional[bool]
    paper_format: Optional[str]
    status: str
    error_log: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, f) -> "PrintedFileResponse":
        return cls(
            id=f.id,
            original_name=f.original_name,
            mime_type=f.mime_type,
            file_size=f.file_size,
            page_count=f.page_count,
            is_color=f.is_color,
            paper_format=f.paper_format,
            status=f.status,
            error_log=f.error_log,
            created_at=f.created_at.isoformat(),
            updated_at=f.updated_at.isoformat(),
        )


# ── Схема відповіді замовлення ─────────────────────────────────────
class PrintJobResponse(BaseModel):
    """Публічне представлення замовлення."""
    id: str
    user_id: int
    copies: int
    duplex: bool
    color_mode: str
    page_range: Optional[str]
    status: str
    files: list[PrintedFileResponse]
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, job) -> "PrintJobResponse":
        return cls(
            id=job.id,
            user_id=job.user_id,
            copies=job.copies,
            duplex=job.duplex,
            color_mode=job.color_mode,
            page_range=job.page_range,
            status=job.status,
            files=[PrintedFileResponse.from_orm(f) for f in job.files],
            created_at=job.created_at.isoformat(),
            updated_at=job.updated_at.isoformat(),
        )
