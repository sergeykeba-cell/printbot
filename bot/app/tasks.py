"""
tasks.py — ARQ фонові задачі для обробки файлів.

Pipeline:
  1. Якщо не PDF → конвертація через LibreOffice (timeout=60s)
  2. Аналіз PDF: кількість сторінок, цветність, формат паперу
  3. Оновлення БД: статус ready_to_print або failed + traceback
"""

import asyncio
import logging
import os
import traceback
import uuid
from pathlib import Path

import fitz  # PyMuPDF

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import PrintedFile, PrintJob

logger = logging.getLogger(__name__)

# Таймаут конвертації LibreOffice (секунди)
LO_TIMEOUT = 60
# Таймаут аналізу PDF (секунди) — захист від zip-бомб
PDF_PARSE_TIMEOUT = 30
# Максимум сторінок для аналізу цветності (не всі — дорого)
COLOR_SAMPLE_PAGES = 5


# ── LibreOffice конвертація ────────────────────────────────────────

async def _convert_to_pdf(src_path: Path, out_dir: Path) -> Path:
    """
    Конвертує документ у PDF через LibreOffice headless.
    Повертає шлях до згенерованого PDF.
    Кидає RuntimeError при помилці або таймауті.
    """
    proc = await asyncio.create_subprocess_exec(
        "soffice", "--headless", "--convert-to", "pdf",
        "--outdir", str(out_dir),
        str(src_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=LO_TIMEOUT
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError(
            f"LibreOffice timeout ({LO_TIMEOUT}s) для файлу: {src_path.name}"
        )

    if proc.returncode != 0:
        raise RuntimeError(
            f"LibreOffice помилка (exit {proc.returncode}): "
            f"{stderr.decode(errors='replace').strip()}"
        )

    # LibreOffice зберігає файл з тим самим ім'ям але розширенням .pdf
    pdf_path = out_dir / (src_path.stem + ".pdf")
    if not pdf_path.exists():
        raise RuntimeError(
            f"LibreOffice не створив PDF за очікуваним шляхом: {pdf_path}"
        )

    logger.info("Конвертовано: %s → %s", src_path.name, pdf_path.name)
    return pdf_path


# ── Аналіз PDF ────────────────────────────────────────────────────

def _detect_paper_format(width_pt: float, height_pt: float) -> str:
    """
    Визначає формат паперу за розмірами сторінки в пунктах.
    A4 ≈ 595×842, A3 ≈ 842×1191 (portrait або landscape).
    """
    dims = tuple(sorted([round(width_pt), round(height_pt)]))

    A4 = (595, 842)
    A3 = (842, 1191)
    tolerance = 20  # пунктів

    def matches(d, ref):
        return all(abs(d[i] - ref[i]) <= tolerance for i in range(2))

    if matches(dims, A4):
        return "A4"
    if matches(dims, A3):
        return "A3"
    return "other"


def _analyze_pdf_sync(pdf_path: Path) -> dict:
    """
    Синхронний аналіз PDF через PyMuPDF.
    Виконується через asyncio.to_thread() — не блокує event loop.

    Повертає: {page_count, is_color, paper_format}
    """
    doc = fitz.open(str(pdf_path))
    try:
        page_count = len(doc)
        if page_count == 0:
            raise ValueError("PDF не містить сторінок.")

        # Формат паперу — беремо з першої сторінки
        first_page = doc[0]
        rect = first_page.rect
        paper_format = _detect_paper_format(rect.width, rect.height)

        # Цветність — перевіряємо вибіркові сторінки
        # Стратегія: рендеримо сторінку у низькій роздільності (72 dpi)
        # і перевіряємо чи є пікселі з вираженим кольором
        is_color = False
        sample_indices = _get_sample_indices(page_count, COLOR_SAMPLE_PAGES)

        for idx in sample_indices:
            page = doc[idx]
            # Низька роздільність для швидкості
            mat = fitz.Matrix(0.3, 0.3)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)

            if _pixmap_has_color(pix):
                is_color = True
                break

        return {
            "page_count": page_count,
            "is_color": is_color,
            "paper_format": paper_format,
        }
    finally:
        doc.close()


def _get_sample_indices(total: int, sample: int) -> list[int]:
    """Рівномірно розподілені індекси сторінок для вибірки."""
    if total <= sample:
        return list(range(total))
    step = total // sample
    return [i * step for i in range(sample)]


def _pixmap_has_color(pix: fitz.Pixmap, threshold: int = 15) -> bool:
    """
    Перевіряє чи містить pixmap кольорові пікселі.
    Метод: для кожного пікселя порівнюємо R, G, B канали.
    Якщо різниця між каналами > threshold — піксель кольоровий.

    threshold=15 — допуск для "майже сірих" пікселів.
    """
    samples = pix.samples  # bytes: RGBRGBRGB...
    n = pix.n             # кількість каналів (3 для RGB)

    if n < 3:
        return False  # grayscale або alpha — не кольоровий

    # Перевіряємо кожен піксель
    for i in range(0, len(samples) - 2, n):
        r, g, b = samples[i], samples[i + 1], samples[i + 2]
        if max(r, g, b) - min(r, g, b) > threshold:
            return True

    return False


# ── ARQ задача ────────────────────────────────────────────────────

async def process_incoming_file(ctx: dict, file_id: str) -> None:
    """
    ARQ задача. Отримує file_id, обробляє файл, оновлює БД.

    Pipeline:
      1. Читаємо запис з БД
      2. Якщо не PDF → конвертуємо через LibreOffice
      3. Аналізуємо PDF (сторінки, цветність, формат)
      4. Оновлюємо статус → ready_to_print або failed
    """
    logger.info("▶ process_incoming_file: file_id=%s", file_id)

    try:
        # ── Сесія 1: читаємо файл ─────────────────────────────────
        async with AsyncSessionLocal() as db:
            file_rec = await db.scalar(
                select(PrintedFile).where(PrintedFile.id == file_id)
            )
            if not file_rec:
                logger.warning("❌ Файл %s не знайдено в БД. Задача скасована.", file_id)
                return

            # Race condition: якщо замовлення вже скасоване — не обробляємо
            job = await db.scalar(
                select(PrintJob).where(PrintJob.id == file_rec.job_id)
            )
            if job and job.status == "failed":
                logger.info("⏭ Job %s скасовано, пропускаємо файл %s.", job.id, file_id)
                return

            src_path = Path(file_rec.file_path)
            mime_type = file_rec.mime_type
            upload_dir = src_path.parent

        # ── Конвертація (якщо не PDF) ─────────────────────────────
        if mime_type == "application/pdf":
            pdf_path = src_path
        else:
            logger.info("🔄 Конвертація %s → PDF...", src_path.name)
            pdf_path = await _convert_to_pdf(src_path, upload_dir)

        # ── Аналіз PDF (з таймаутом — захист від zip-бомб) ────────
        logger.info("🔍 Аналіз PDF: %s", pdf_path.name)
        try:
            analysis = await asyncio.wait_for(
                asyncio.to_thread(_analyze_pdf_sync, pdf_path),
                timeout=PDF_PARSE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"Таймаут аналізу PDF ({PDF_PARSE_TIMEOUT}s). "
                "Можливо файл пошкоджений або занадто великий."
            )

        # ── Сесія 2: оновлюємо запис ──────────────────────────────
        async with AsyncSessionLocal() as db:
            file_rec = await db.scalar(
                select(PrintedFile).where(PrintedFile.id == file_id)
            )
            if not file_rec:
                logger.warning("⚠ Файл %s видалено під час обробки.", file_id)
                return

            file_rec.pdf_path = str(pdf_path)
            file_rec.page_count = analysis["page_count"]
            file_rec.is_color = analysis["is_color"]
            file_rec.paper_format = analysis["paper_format"]
            file_rec.status = "ready_to_print"
            file_rec.error_log = None
            # Оновлюємо статус замовлення
            job = await db.scalar(
                select(PrintJob).where(PrintJob.id == file_rec.job_id)
            )
            if job:
                job.status = "ready_to_print"
            await db.commit()

        logger.info(
            "✅ Файл %s оброблено: %d стор., %s, %s",
            file_id,
            analysis["page_count"],
            "color" if analysis["is_color"] else "bw",
            analysis["paper_format"],
        )

    except Exception:
        error_trace = traceback.format_exc()
        logger.error("❌ Помилка обробки file_id=%s:\n%s", file_id, error_trace)

        async with AsyncSessionLocal() as db:
            file_rec = await db.scalar(
                select(PrintedFile).where(PrintedFile.id == file_id)
            )
            if file_rec:
                file_rec.status = "failed"
                file_rec.error_log = error_trace
                await db.commit()


# ── Конфігурація ARQ воркера ──────────────────────────────────────

import os
from arq.connections import RedisSettings

class WorkerSettings:
    functions = [process_incoming_file]
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    max_jobs = 5
    job_timeout = 180
