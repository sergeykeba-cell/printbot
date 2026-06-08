"""
api_client.py — httpx клієнт для FastAPI інстансу.
"""

import logging
from pathlib import Path

import httpx
import aiofiles

from app.config import settings

logger = logging.getLogger(__name__)

HEADERS = {"X-API-Key": settings.INSTANCE_API_KEY}
TIMEOUT = httpx.Timeout(30.0)


async def create_job(user_id: int) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{settings.INSTANCE_API_URL}/api/print/jobs",
            params={"user_id": user_id},
            json={"copies": 1, "duplex": False, "color_mode": "bw"},
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def upload_file(job_id: str, file_path: Path, file_name: str) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()
        import mimetypes
        _MIME_MAP = {
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".odt":  "application/vnd.oasis.opendocument.text",
            ".doc":  "application/msword",
            ".pdf":  "application/pdf",
            ".png":  "image/png",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
        }
        from pathlib import Path as _Path
        _ext = _Path(file_name).suffix.lower()
        mime = _MIME_MAP.get(_ext) or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        resp = await client.post(
            f"{settings.INSTANCE_API_URL}/api/print/upload",
            params={"job_id": job_id},
            files={"file": (file_name, content, mime)},
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def update_job(job_id: str, opts: dict) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        payload = {
            "copies": opts["copies"],
            "duplex": opts["duplex"],
            "color_mode": opts["color_mode"],
            "page_range": opts.get("page_range"),
            "orientation": opts.get("orientation"),
            "photo_size": opts.get("photo_size"),
        }
        resp = await client.patch(
            f"{settings.INSTANCE_API_URL}/api/print/jobs/{job_id}",
            json=payload,
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def cancel_job(job_id: str) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.delete(
            f"{settings.INSTANCE_API_URL}/api/print/jobs/{job_id}",
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()

async def get_job(job_id: str) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            f"{settings.INSTANCE_API_URL}/api/print/jobs/{job_id}",
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()

async def update_job_status(job_id: str, status: str) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.patch(
            f"{settings.INSTANCE_API_URL}/api/print/jobs/{job_id}/status",
            json={"status": status},
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def list_jobs(status_filter: str = None, limit: int = 20) -> list:
    params = {"limit": limit}
    if status_filter:
        params["status_filter"] = status_filter
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            f"{settings.INSTANCE_API_URL}/api/print/jobs",
            params=params,
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def download_file(file_id: str) -> tuple[bytes, str]:
    """Завантажує файл з API. Повертає (bytes, content-disposition)."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            f"{settings.INSTANCE_API_URL}/api/print/files/{file_id}/download",
            headers=HEADERS,
        )
        resp.raise_for_status()
        disposition = resp.headers.get("content-disposition", f'filename="{file_id}"')
        return resp.content, disposition
