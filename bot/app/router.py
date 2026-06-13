"""
router.py — FastAPI ендпоінти для прийому та керування файлами друку.

Зміни відносно попередньої версії:
  - Імпортовано limiter з app.core.rate_limiter.
  - Додано @limiter.limit() декоратори на критичні ендпоінти:
      POST /api/print/jobs   → 20/minute (створення замовлень)
      POST /api/print/upload → 10/minute (завантаження файлів)
  - Декоратор @limiter.limit() ЗАВЖДИ іде після @router.<method>().
"""

import logging
import mimetypes
import os
import re
import unicodedata
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request, Security, status
from pydantic import BaseModel, field_validator
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_redis_pool
from app.models import PrintJob, PrintedFile
from app.schemas import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE,
    PrintConfigSchema,
    PrintJobResponse,
    FileUploadResponse,
)
from app.core.rate_limiter import limiter

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _verify_key(
    api_key_header: str = Security(_api_key_header),
    api_key: str = Query(None),
) -> str:
    expected = os.environ.get("INSTANCE_API_KEY", "")
    key = api_key_header or api_key
    if not expected or key != expected:
        raise HTTPException(status_code=403, detail="Доступ заборонено.")
    return key


router = APIRouter(
    prefix="/api/print",
    tags=["Print"],
    dependencies=[Depends(_verify_key)],
)

UPLOAD_BASE = Path(os.environ.get("UPLOAD_DIR", "/app/uploads")).resolve()
UPLOAD_BASE.mkdir(parents=True, exist_ok=True)
CHUNK_SIZE = 256 * 1024


def _safe_filename(original: str) -> str:
    name = unicodedata.normalize("NFD", original)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w\s\-.]", "", name).strip()
    name = re.sub(r"\s+", "_", name)
    path = Path(name)
    stem = path.stem[:50] or "file"
    suffix = path.suffix.lower()
    return f"{uuid.uuid4().hex}_{stem}{suffix}"


def _validate_upload_path(file_path: Path) -> None:
    try:
        file_path.resolve().relative_to(UPLOAD_BASE)
    except ValueError:
        raise HTTPException(status_code=400, detail="Недопустимий шлях до файлу.")


def _validate_mime(filename: str, content_type: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Розширення '{suffix}' не підтримується. "
                   f"Дозволені: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    mime = content_type or mimetypes.guess_type(filename)[0] or ""
    mime = mime.split(";")[0].strip().lower()
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"MIME-тип '{mime}' не підтримується.")
    return mime


# ── Ендпоінти ──────────────────────────────────────────────────────

@router.post("/jobs", status_code=status.HTTP_201_CREATED, response_model=PrintJobResponse)
@limiter.limit("20/minute")
async def create_job(
    request: Request,                          # обов'язковий для slowapi
    config: PrintConfigSchema,
    user_id: int = Query(..., description="Telegram user ID"),
    db: AsyncSession = Depends(get_db),
):
    """Створення замовлення. Ліміт: 20 запитів/хвилину на IP."""
    job = PrintJob(
        user_id=user_id,
        copies=config.copies,
        duplex=config.duplex,
        color_mode=config.color_mode,
        page_range=config.page_range,
        status="draft",
    )
    db.add(job)
    await db.commit()
    result = await db.execute(
        select(PrintJob).options(selectinload(PrintJob.files)).where(PrintJob.id == job.id)
    )
    job = result.scalar_one()
    logger.info("Створено замовлення job_id=%s user_id=%s", job.id, user_id)
    return PrintJobResponse.from_orm(job)


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED, response_model=FileUploadResponse)
@limiter.limit("10/minute")
async def upload_file(
    request: Request,                          # обов'язковий для slowapi
    job_id: str = Query(..., description="ID замовлення"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis_pool),
):
    """Завантаження файлу. Ліміт: 10 запитів/хвилину на IP."""
    job = await db.scalar(select(PrintJob).where(PrintJob.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено.")
    if job.status not in ("draft", "processing"):
        raise HTTPException(
            status_code=400,
            detail=f"Неможливо додати файл до замовлення зі статусом '{job.status}'.",
        )

    mime = _validate_mime(file.filename or "unknown", file.content_type or "")
    safe_name = _safe_filename(file.filename or "unknown")
    file_path = UPLOAD_BASE / safe_name
    _validate_upload_path(file_path)

    total_size = 0
    tmp_path = file_path.with_suffix(".tmp")

    try:
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        async with aiofiles.open(fd, "wb") as out:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Файл перевищує максимальний розмір "
                               f"({MAX_FILE_SIZE // 1024 // 1024} МБ).",
                    )
                await out.write(chunk)
        tmp_path.rename(file_path)
    except HTTPException:
        tmp_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        logger.error("Помилка запису файлу: %s", e)
        raise HTTPException(status_code=500, detail="Помилка збереження файлу.")

    file_rec = PrintedFile(
        job_id=job_id,
        original_name=file.filename or "unknown",
        safe_name=safe_name,
        file_path=str(file_path),
        mime_type=mime,
        file_size=total_size,
        status="processing",
    )
    db.add(file_rec)
    job.status = "processing"
    await db.commit()
    await db.refresh(file_rec)
    await redis.enqueue_job("process_incoming_file", file_rec.id)
    logger.info("Файл прийнято: file_id=%s job_id=%s size=%d", file_rec.id, job_id, total_size)
    return FileUploadResponse(
        file_id=file_rec.id,
        job_id=job_id,
        original_name=file_rec.original_name,
        file_size=total_size,
        mime_type=mime,
        status="processing",
        message="Файл прийнято. Обробка розпочата.",
    )


@router.get("/jobs/{job_id}", response_model=PrintJobResponse)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.scalar(
        select(PrintJob).where(PrintJob.id == job_id).options(selectinload(PrintJob.files))
    )
    if not job:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено.")
    return PrintJobResponse.from_orm(job)


@router.patch("/jobs/{job_id}", response_model=PrintJobResponse)
async def update_job(
    job_id: str, config: PrintConfigSchema, db: AsyncSession = Depends(get_db)
):
    job = await db.scalar(select(PrintJob).where(PrintJob.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено.")
    if job.status not in ("draft", "processing", "ready_to_print"):
        raise HTTPException(
            status_code=400,
            detail=f"Неможливо змінити замовлення зі статусом '{job.status}'.",
        )
    job.copies = config.copies
    job.duplex = config.duplex
    job.color_mode = config.color_mode
    job.page_range = config.page_range
    job.orientation = config.orientation
    job.photo_size = config.photo_size
    await db.commit()
    result = await db.execute(
        select(PrintJob).options(selectinload(PrintJob.files)).where(PrintJob.id == job.id)
    )
    job = result.scalar_one()
    return PrintJobResponse.from_orm(job)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_200_OK)
async def cancel_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.scalar(select(PrintJob).where(PrintJob.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено.")
    if job.status == "printed":
        raise HTTPException(
            status_code=400, detail="Неможливо скасувати надруковане замовлення."
        )
    job.status = "failed"
    await db.commit()
    logger.info("Замовлення скасовано: job_id=%s", job_id)
    return {"status": "cancelled", "job_id": job_id}


@router.get("/files/{file_id}/download")
async def download_file(file_id: str, db: AsyncSession = Depends(get_db)):
    """Повертає файл для скачування оператором."""
    from fastapi.responses import FileResponse

    file_rec = await db.scalar(select(PrintedFile).where(PrintedFile.id == file_id))
    if not file_rec:
        raise HTTPException(status_code=404, detail="Файл не знайдено.")
    file_path = Path(file_rec.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл відсутній на диску.")
    return FileResponse(
        path=str(file_path),
        filename=file_rec.original_name,
        media_type=file_rec.mime_type,
    )


@router.get("/jobs", response_model=list[PrintJobResponse])
async def list_jobs(
    status_filter: str | None = Query(None, description="Фільтр по статусу"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(PrintJob)
        .options(selectinload(PrintJob.files))
        .order_by(PrintJob.created_at.desc())
    )
    if status_filter:
        query = query.where(PrintJob.status == status_filter)
    query = query.limit(limit)
    result = await db.execute(query)
    jobs = result.scalars().all()
    return [PrintJobResponse.from_orm(j) for j in jobs]


class StatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"draft", "processing", "ready_to_print", "printed", "failed"}
        if v not in allowed:
            raise ValueError(f"Статус має бути одним з: {allowed}")
        return v


STATUS_TRANSITIONS = {
    "draft":          {"processing", "failed"},
    "processing":     {"ready_to_print", "printed", "failed"},
    "ready_to_print": {"printed", "failed"},
    "printed":        set(),
    "failed":         {"processing"},
}


@router.patch("/jobs/{job_id}/status", response_model=PrintJobResponse)
async def update_job_status(
    job_id: str,
    body: StatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    job = await db.scalar(select(PrintJob).where(PrintJob.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено.")
    allowed = STATUS_TRANSITIONS.get(job.status, set())
    if body.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Перехід {job.status} → {body.status} заборонено.",
        )
    job.status = body.status
    await db.commit()
    result = await db.execute(
        select(PrintJob).options(selectinload(PrintJob.files)).where(PrintJob.id == job.id)
    )
    return PrintJobResponse.from_orm(result.scalar_one())
