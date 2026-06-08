"""
router.py — FastAPI ендпоінти для прийому та керування файлами друку.
"""

import logging
import mimetypes
import os
import re
import unicodedata
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy import select
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/print", tags=["Print"])

UPLOAD_BASE = Path(os.environ.get("UPLOAD_DIR", "/app/uploads")).resolve()
UPLOAD_BASE.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 256 * 1024  # 256 KB


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


@router.post("/jobs", status_code=status.HTTP_201_CREATED, response_model=PrintJobResponse)
async def create_job(
    config: PrintConfigSchema,
    user_id: int = Query(..., description="Telegram user ID"),
    db: AsyncSession = Depends(get_db),
):
    """Створити нове замовлення з параметрами друку."""
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
    await db.refresh(job)
    logger.info("Створено замовлення job_id=%s user_id=%s", job.id, user_id)
    return PrintJobResponse.from_orm(job)


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED, response_model=FileUploadResponse)
async def upload_file(
    job_id: str = Query(..., description="ID замовлення"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis_pool),
):
    """Потоковий прийом файлу без завантаження в RAM."""
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
    """Отримати статус замовлення з усіма файлами."""
    from sqlalchemy.orm import selectinload
    job = await db.scalar(
        select(PrintJob).where(PrintJob.id == job_id).options(selectinload(PrintJob.files))
    )
    if not job:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено.")
    return PrintJobResponse.from_orm(job)


@router.patch("/jobs/{job_id}", response_model=PrintJobResponse)
async def update_job(job_id: str, config: PrintConfigSchema, db: AsyncSession = Depends(get_db)):
    """Оновити параметри друку замовлення."""
    job = await db.scalar(select(PrintJob).where(PrintJob.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено.")
    if job.status not in ("draft", "processing"):
        raise HTTPException(
            status_code=400,
            detail=f"Неможливо змінити замовлення зі статусом '{job.status}'.",
        )
    job.copies = config.copies
    job.duplex = config.duplex
    job.color_mode = config.color_mode
    job.page_range = config.page_range
    await db.commit()
    await db.refresh(job)
    return PrintJobResponse.from_orm(job)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_200_OK)
async def cancel_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Скасувати замовлення."""
    job = await db.scalar(select(PrintJob).where(PrintJob.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено.")
    if job.status == "printed":
        raise HTTPException(status_code=400, detail="Неможливо скасувати надруковане замовлення.")
    job.status = "failed"
    await db.commit()
    logger.info("Замовлення скасовано: job_id=%s", job_id)
    return {"status": "cancelled", "job_id": job_id}