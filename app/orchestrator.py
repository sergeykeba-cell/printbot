"""
orchestrator.py — REST API Менеджера інстансів.

Ендпоінти:
  POST   /api/instances/create              — Створити новий інстанс
  GET    /api/instances                     — Список всіх інстансів (без секретів)
  GET    /api/instances/{id}/logs           — Логи (error_log або docker logs)
  POST   /api/instances/{id}/retry          — Перезапустити провізіонінг
  POST   /api/instances/{id}/action         — Lifecycle: stop / start / restart
  DELETE /api/instances/{id}                — Видалити інстанс (з підтвердженням)

Безпека:
  - X-API-Key на всіх ендпоінтах
  - Regex валідація субдомену (закриває RCE через bash injection)
  - InstanceAction Enum (закриває docker command injection)
  - Секрети в Pydantic response схемах НІКОЛИ не повертаються
"""

import os
import re
import secrets
import asyncio
import subprocess
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.manager_db import get_manager_db, get_redis_pool
from app.models import InstanceRegistry
from app.security import encrypt_secret, decrypt_secret, verify_manager_access

router = APIRouter(
    prefix="/api/instances",
    tags=["Instance Management"],
    dependencies=[Depends(verify_manager_access)],  # Автентифікація на весь роутер
)

# ── Валідація субдомену ────────────────────────────────────────────
# Закриває RCE через bash injection: дозволяє лише [a-z0-9-]
_SUBDOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$")


# ── Pydantic схеми ─────────────────────────────────────────────────

class CreateInstanceSchema(BaseModel):
    subdomain: str = Field(..., min_length=3, max_length=63)
    tg_bot_token: str = Field(..., min_length=20)

    @field_validator("subdomain")
    @classmethod
    def validate_subdomain(cls, v: str) -> str:
        v = v.lower().strip()
        if not _SUBDOMAIN_RE.match(v):
            raise ValueError(
                "Субдомен: лише малі латинські літери, цифри, дефіс; "
                "не може починатись або закінчуватись дефісом."
            )
        return v


class InstanceResponse(BaseModel):
    """Публічне представлення інстансу — БЕЗ секретів."""
    id: str
    subdomain: str
    status: str
    error_log: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, inst: InstanceRegistry) -> "InstanceResponse":
        return cls(
            id=inst.id,
            subdomain=inst.subdomain,
            status=inst.status,
            error_log=inst.error_log,
            created_at=inst.created_at.isoformat(),
            updated_at=inst.updated_at.isoformat(),
        )


class InstanceAction(str, Enum):
    """
    Дозволені дії над інстансом.
    Enum закриває docker command injection — будь-яке інше значення
    відхиляється Pydantic на рівні валідації.
    """
    stop = "stop"
    start = "start"
    restart = "restart"


class ActionSchema(BaseModel):
    action: InstanceAction


# ── Допоміжна функція: виконати docker compose команду ────────────

def _run_compose_action(subdomain: str, action: str, timeout: int = 30) -> str:
    """Синхронна; викликається через asyncio.to_thread()."""
    project_dir = f"/opt/printbot/instances/{subdomain}"
    result = subprocess.run(
        ["docker", "compose", "-p", f"printbot_{subdomain}", action],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def _get_docker_logs(subdomain: str, tail: int = 100, timeout: int = 15) -> str:
    """Синхронна; викликається через asyncio.to_thread()."""
    project_dir = f"/opt/printbot/instances/{subdomain}"
    result = subprocess.run(
        [
            "docker", "compose", "-p", f"printbot_{subdomain}",
            "logs", f"--tail={tail}", "--no-color",
        ],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=timeout,  # Захист від зависання при поганому стані контейнера
    )
    return result.stdout + result.stderr


# ── Ендпоінти ──────────────────────────────────────────────────────

@router.post("/create", status_code=status.HTTP_202_ACCEPTED)
async def create_new_print_shop(
    payload: CreateInstanceSchema,
    db: AsyncSession = Depends(get_manager_db),
    redis_pool=Depends(get_redis_pool),
):
    # Перевірка унікальності субдомену
    existing = await db.scalar(
        select(InstanceRegistry).where(InstanceRegistry.subdomain == payload.subdomain)
    )
    if existing:
        raise HTTPException(status_code=400, detail="Цей субдомен вже використовується.")

    db_password = secrets.token_urlsafe(24)

    new_instance = InstanceRegistry(
        subdomain=payload.subdomain,
        encrypted_tg_bot_token=encrypt_secret(payload.tg_bot_token),
        encrypted_db_password=encrypt_secret(db_password),
        status="provisioning",
    )
    db.add(new_instance)
    await db.commit()
    await db.refresh(new_instance)

    # В чергу йде ТІЛЬКИ instance_id — секрети не потрапляють в Redis
    await redis_pool.enqueue_job("deploy_instance", new_instance.id)

    return {
        "status": "accepted",
        "instance_id": new_instance.id,
        "url": f"https://{payload.subdomain}.printbot.app",
    }


@router.get("", response_model=list[InstanceResponse])
async def list_instances(
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_manager_db),
):
    """Повертає список інстансів. Секрети НІКОЛИ не включаються у відповідь."""
    query = select(InstanceRegistry).order_by(InstanceRegistry.created_at.desc())

    if status_filter:
        allowed = {"provisioning", "active", "failed", "stopped"}
        if status_filter not in allowed:
            raise HTTPException(status_code=400, detail=f"Невідомий статус: {status_filter}")
        query = query.where(InstanceRegistry.status == status_filter)

    query = query.limit(limit).offset(offset)
    result = await db.scalars(query)
    instances = result.all()
    return [InstanceResponse.from_orm(i) for i in instances]


@router.get("/{instance_id}/logs")
async def get_instance_logs(
    instance_id: str,
    tail: int = 100,
    db: AsyncSession = Depends(get_manager_db),
):
    """
    Якщо статус 'failed' — повертає error_log з БД.
    Якщо статус 'active'/'stopped' — виконує docker compose logs --tail=N.
    """
    instance = await db.scalar(
        select(InstanceRegistry).where(InstanceRegistry.id == instance_id)
    )
    if not instance:
        raise HTTPException(status_code=404, detail="Інстанс не знайдено")

    if instance.status == "failed":
        return {
            "source": "error_log",
            "subdomain": instance.subdomain,
            "logs": instance.error_log or "Лог відсутній.",
        }

    # Для активних/зупинених — живі логи з docker compose
    try:
        logs = await asyncio.to_thread(
            _get_docker_logs, instance.subdomain, tail
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Таймаут отримання логів.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "source": "docker_compose",
        "subdomain": instance.subdomain,
        "logs": logs,
    }


@router.post("/{instance_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_failed_provisioning(
    instance_id: str,
    db: AsyncSession = Depends(get_manager_db),
    redis_pool=Depends(get_redis_pool),
):
    instance = await db.scalar(
        select(InstanceRegistry).where(InstanceRegistry.id == instance_id)
    )
    if not instance:
        raise HTTPException(status_code=404, detail="Інстанс не знайдено")

    # Блокуємо double-retry: тільки з "failed" статусу дозволено перезапуск
    if instance.status in ("active", "provisioning"):
        raise HTTPException(
            status_code=400,
            detail=f"Неможливо перезапустити інстанс у статусі '{instance.status}'.",
        )

    instance.status = "provisioning"
    instance.error_log = None
    await db.commit()

    # Тільки ID — секрети воркер читає сам з БД
    await redis_pool.enqueue_job("deploy_instance", instance.id)
    return {"status": "retrying", "instance_id": instance_id}


@router.post("/{instance_id}/action", status_code=status.HTTP_200_OK)
async def instance_lifecycle_action(
    instance_id: str,
    payload: ActionSchema,
    db: AsyncSession = Depends(get_manager_db),
):
    """
    Lifecycle керування: stop / start / restart.
    InstanceAction Enum відхиляє будь-яку команду поза білим списком —
    захист від docker command injection (наприклад 'down --volumes').
    """
    instance = await db.scalar(
        select(InstanceRegistry).where(InstanceRegistry.id == instance_id)
    )
    if not instance:
        raise HTTPException(status_code=404, detail="Інстанс не знайдено")

    if instance.status == "provisioning":
        raise HTTPException(
            status_code=400, detail="Неможливо керувати інстансом під час провізіонінгу."
        )

    try:
        output = await asyncio.to_thread(
            _run_compose_action, instance.subdomain, payload.action.value
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Таймаут виконання команди Docker.")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Оновлюємо статус після stop
    if payload.action == InstanceAction.stop:
        instance.status = "stopped"
        await db.commit()
    elif payload.action in (InstanceAction.start, InstanceAction.restart):
        instance.status = "active"
        await db.commit()

    return {"status": "ok", "action": payload.action, "output": output}


@router.delete("/{instance_id}", status_code=status.HTTP_200_OK)
async def delete_instance(
    instance_id: str,
    confirm: bool = False,
    db: AsyncSession = Depends(get_manager_db),
):
    """
    Видаляє запис з реєстру.
    Зупиняє контейнери але НЕ видаляє volumes (дані в безпеці).
    Для повного знесення — окрема ручна операція 'docker compose down -v'.
    Потрібен query param: ?confirm=true
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Передайте ?confirm=true для підтвердження видалення.",
        )

    instance = await db.scalar(
        select(InstanceRegistry).where(InstanceRegistry.id == instance_id)
    )
    if not instance:
        raise HTTPException(status_code=404, detail="Інстанс не знайдено")

    subdomain = instance.subdomain

    # Зупиняємо контейнери (без видалення volumes)
    try:
        await asyncio.to_thread(_run_compose_action, subdomain, "stop")
    except Exception:
        pass  # Якщо вже зупинено — ігноруємо

    await db.delete(instance)
    await db.commit()

    return {
        "status": "deleted",
        "subdomain": subdomain,
        "note": "Volumes збережено. Для повного видалення: docker compose -p printbot_{subdomain} down -v",
    }


@router.post("/{instance_id}/backup", status_code=status.HTTP_202_ACCEPTED)
async def backup_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_manager_db),
):
    """
    Запускає backup_instance.sh для збереження БД та конфігурації.
    Виконується асинхронно — повертає одразу, не чекає завершення.
    """
    instance = await db.scalar(
        select(InstanceRegistry).where(InstanceRegistry.id == instance_id)
    )
    if not instance:
        raise HTTPException(status_code=404, detail="Інстанс не знайдено")

    if instance.status not in ("active", "stopped"):
        raise HTTPException(
            status_code=400,
            detail=f"Бекап неможливий у статусі '{instance.status}'.",
        )

    subdomain = instance.subdomain
    script = "/opt/printbot/infrastructure/backup_instance.sh"

    async def _run():
        try:
            await asyncio.to_thread(
                subprocess.run,
                ["bash", script, subdomain],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except Exception as e:
            print(f"❌ Backup failed for {subdomain}: {e}")

    asyncio.create_task(_run())

    return {
        "status": "started",
        "subdomain": subdomain,
        "backup_dir": f"/opt/printbot/backups/{subdomain}",
    }
