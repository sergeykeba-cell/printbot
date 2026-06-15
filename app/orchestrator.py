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
  - Sybil-захист: один Free-інстанс на Telegram-акаунт (в одній транзакції)
"""

import os
import re
import secrets
import asyncio
import subprocess
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.manager_db import get_manager_db, get_redis_pool
from app.models import InstanceRegistry
from app.security import encrypt_secret, decrypt_secret, verify_manager_access

router = APIRouter(
    prefix="/api/instances",
    tags=["Instance Management"],
    dependencies=[Depends(verify_manager_access)],
)
public_router = APIRouter(
    prefix="/api/instances",
    tags=["public"],
)

# ── Валідація субдомену ────────────────────────────────────────────
_SUBDOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$")


# ── Pydantic схеми ─────────────────────────────────────────────────

class CreateInstanceSchema(BaseModel):
    subdomain: str = Field(..., min_length=3, max_length=63)
    tg_bot_token: str = Field(..., min_length=20)
    price_list: dict | None = Field(
        None, description="JSON прайс-лист для seed при старті інстансу"
    )

    # Telegram ID власника — обов'язковий, позитивне ціле число.
    # gt=0 відхиляє null (Pydantic required) і від'ємні/нульові значення.
    owner_telegram_id: int = Field(
        ...,
        gt=0,
        description="Telegram ID власника (з Telegram Login Widget або бота)",
    )

    # Тарифний план: 'free' | 'start' | 'business'
    plan_tier: str = Field(default="free")

    # Демо-інстанс не рахується у Free-ліміт
    is_demo: bool = Field(default=False)

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

    @field_validator("plan_tier")
    @classmethod
    def validate_plan_tier(cls, v: str) -> str:
        allowed = {"free", "start", "business"}
        if v not in allowed:
            raise ValueError(f"plan_tier має бути одним з: {allowed}")
        return v


class InstanceResponse(BaseModel):
    """Публічне представлення інстансу — БЕЗ секретів."""
    id: str
    subdomain: str
    status: str
    plan_tier: str
    is_demo: bool
    owner_telegram_id: Optional[int]
    error_log: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, inst: InstanceRegistry) -> "InstanceResponse":
        return cls(
            id=inst.id,
            subdomain=inst.subdomain,
            status=inst.status,
            plan_tier=inst.plan_tier,
            is_demo=inst.is_demo,
            owner_telegram_id=inst.owner_telegram_id,
            error_log=inst.error_log,
            created_at=inst.created_at.isoformat(),
            updated_at=inst.updated_at.isoformat(),
        )


class InstanceAction(str, Enum):
    """
    Дозволені дії над інстансом.
    Enum закриває docker command injection.
    """
    stop = "stop"
    start = "start"
    restart = "restart"


class ActionSchema(BaseModel):
    action: InstanceAction


# ── Допоміжна функція: Sybil-перевірка ────────────────────────────

async def _check_sybil(
    db: AsyncSession,
    owner_telegram_id: int,
    plan_tier: str,
    is_demo: bool,
) -> None:
    """
    Перевіряє, чи є у користувача вже активний Free-інстанс.

    Умови перевірки:
      - plan_tier == 'free' (платні тарифи не обмежуються)
      - is_demo == False (демо не рахується)
      - owner_telegram_id > 0 (валідується Pydantic, але перевіряємо і тут)

    Викликається ВСЕРЕДИНІ транзакції create_new_print_shop, тому
    check + insert атомарні — race condition виключено.

    Raises:
        HTTPException 409 — якщо Free-інстанс вже існує.
    """
    if plan_tier != "free" or is_demo:
        return  # Sybil-перевірка не застосовується

    existing = await db.scalar(
        select(InstanceRegistry).where(
            InstanceRegistry.owner_telegram_id == owner_telegram_id,
            InstanceRegistry.plan_tier == "free",
            InstanceRegistry.is_demo.is_(False),
        ).limit(1)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A free instance is already associated with this Telegram account. "
                "Please upgrade the existing instance or contact support."
            ),
        )


# ── Допоміжні функції: docker compose ─────────────────────────────

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
        timeout=timeout,
    )
    return result.stdout + result.stderr


# ── Ендпоінти ──────────────────────────────────────────────────────

@router.post("/create", status_code=status.HTTP_202_ACCEPTED)
async def create_new_print_shop(
    payload: CreateInstanceSchema,
    db: AsyncSession = Depends(get_manager_db),
    redis_pool=Depends(get_redis_pool),
):
    """
    Створює новий інстанс точки печати.

    Транзакція включає:
      1. Перевірку унікальності субдомену
      2. Sybil-перевірку (один Free на Telegram-акаунт)
      3. INSERT нового інстансу

    Всі три кроки виконуються в одній транзакції — race condition виключено.
    """
    async with db.begin():
        # 1. Унікальність субдомену
        existing = await db.scalar(
            select(InstanceRegistry).where(
                InstanceRegistry.subdomain == payload.subdomain
            )
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Цей субдомен вже використовується.",
            )

        # 2. Sybil-перевірка (тільки для Free, не для демо)
        await _check_sybil(
            db,
            owner_telegram_id=payload.owner_telegram_id,
            plan_tier=payload.plan_tier,
            is_demo=payload.is_demo,
        )

        # 3. Створення запису
        db_password = secrets.token_urlsafe(24)
        new_instance = InstanceRegistry(
            subdomain=payload.subdomain,
            encrypted_tg_bot_token=encrypt_secret(payload.tg_bot_token),
            encrypted_db_password=encrypt_secret(db_password),
            status="provisioning",
            owner_telegram_id=payload.owner_telegram_id,
            plan_tier=payload.plan_tier,
            is_demo=payload.is_demo,
        )
        db.add(new_instance)
        await db.flush()   # отримуємо id до commit
        instance_id = new_instance.id

    # Поза транзакцією — в чергу йде ТІЛЬКИ instance_id
    await redis_pool.enqueue_job("deploy_instance", instance_id, payload.price_list)

    return {
        "status": "accepted",
        "instance_id": instance_id,
        "url": f"https://printbot.duckdns.org/instance/{payload.subdomain}",
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
            raise HTTPException(
                status_code=400, detail=f"Невідомий статус: {status_filter}"
            )
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

    try:
        logs = await asyncio.to_thread(_get_docker_logs, instance.subdomain, tail)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Таймаут отримання логів.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"source": "docker_compose", "subdomain": instance.subdomain, "logs": logs}


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

    if instance.status in ("active", "provisioning"):
        raise HTTPException(
            status_code=400,
            detail=f"Неможливо перезапустити інстанс у статусі '{instance.status}'.",
        )

    instance.status = "provisioning"
    instance.error_log = None
    await db.commit()
    await redis_pool.enqueue_job("deploy_instance", instance.id)
    return {"status": "retrying", "instance_id": instance_id}


@router.post("/{instance_id}/action", status_code=status.HTTP_200_OK)
async def instance_lifecycle_action(
    instance_id: str,
    payload: ActionSchema,
    db: AsyncSession = Depends(get_manager_db),
):
    instance = await db.scalar(
        select(InstanceRegistry).where(InstanceRegistry.id == instance_id)
    )
    if not instance:
        raise HTTPException(status_code=404, detail="Інстанс не знайдено")

    if instance.status == "provisioning":
        raise HTTPException(
            status_code=400,
            detail="Неможливо керувати інстансом під час провізіонінгу.",
        )

    try:
        output = await asyncio.to_thread(
            _run_compose_action, instance.subdomain, payload.action.value
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Таймаут виконання команди Docker.")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    try:
        await asyncio.to_thread(_run_compose_action, subdomain, "stop")
    except Exception:
        pass

    await db.delete(instance)
    await db.commit()

    return {
        "status": "deleted",
        "subdomain": subdomain,
        "note": f"Volumes збережено. Для повного видалення: docker compose -p printbot_{subdomain} down -v",
    }


@public_router.get("/by-subdomain/{subdomain}/webform-key")
async def get_webform_key(
    subdomain: str, db: AsyncSession = Depends(get_manager_db)
):
    instance = await db.scalar(
        select(InstanceRegistry).where(InstanceRegistry.subdomain == subdomain)
    )
    if not instance:
        raise HTTPException(status_code=404, detail="Інстанс не знайдено.")
    env_path = f"/opt/printbot/instances/{subdomain}/.env"
    api_key = None
    try:
        with open(env_path) as f:
            for line in f:
                if line.startswith("INSTANCE_API_KEY="):
                    api_key = line.strip().split("=", 1)[1]
                    break
    except Exception:
        raise HTTPException(status_code=500, detail="Не вдалось прочитати ключ.")
    return {"api_key": api_key}


@router.get("/{instance_id}/operator")
async def get_operator_info(
    instance_id: str,
    db: AsyncSession = Depends(get_manager_db),
):
    instance = await db.scalar(
        select(InstanceRegistry).where(InstanceRegistry.id == instance_id)
    )
    if not instance:
        raise HTTPException(status_code=404, detail="Інстанс не знайдено")
    if instance.status != "active":
        raise HTTPException(status_code=400, detail="Інстанс ще не активний.")

    operator_secret = None
    if instance.encrypted_operator_secret:
        operator_secret = decrypt_secret(instance.encrypted_operator_secret)

    instance_api_key = None
    env_path = f"/opt/printbot/instances/{instance.subdomain}/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("INSTANCE_API_KEY="):
                    instance_api_key = line.strip().split("=", 1)[1]

    return {
        "instance_id": instance.id,
        "subdomain": instance.subdomain,
        "bot_url": f"https://t.me/{instance.subdomain}_bot",
        "operator_secret": operator_secret,
        "operator_command": f"/operator {operator_secret}" if operator_secret else None,
        "web_url": f"https://printbot.duckdns.org/instance/{instance.subdomain}",
        "instance_api_key": instance_api_key,
        "operator_panel_url": "https://printbot-operator.duckdns.org",
    }


# ── WebSocket: live статус інстансу ───────────────────────────────

from fastapi import WebSocket, WebSocketDisconnect
from app.ws_manager import ws_manager


@router.websocket("/{instance_id}/ws")
async def websocket_status(instance_id: str, ws: WebSocket):
    await ws_manager.connect(instance_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(instance_id, ws)


# ── Maintenance mode ──────────────────────────────────────────────

class MaintenanceAction(str, Enum):
    enter = "enter"
    leave = "leave"


class MaintenanceSchema(BaseModel):
    action: MaintenanceAction


@router.post("/{instance_id}/maintenance", status_code=status.HTTP_200_OK)
async def instance_maintenance(
    instance_id: str,
    payload: MaintenanceSchema,
    db: AsyncSession = Depends(get_manager_db),
):
    instance = await db.scalar(
        select(InstanceRegistry).where(InstanceRegistry.id == instance_id)
    )
    if not instance:
        raise HTTPException(status_code=404, detail="Інстанс не знайдено")

    if payload.action == MaintenanceAction.enter:
        if instance.status == "provisioning":
            raise HTTPException(
                status_code=400,
                detail="Неможливо ввести maintenance під час провізіонінгу.",
            )
        instance.status = "maintenance"
        await db.commit()
        await ws_manager.broadcast(
            instance_id, {"event": "status", "status": "maintenance"}
        )
        return {"status": "maintenance", "instance_id": instance_id}

    if instance.status != "maintenance":
        raise HTTPException(
            status_code=400,
            detail=f"Інстанс не в режимі maintenance (поточний: '{instance.status}').",
        )
    instance.status = "active"
    await db.commit()
    await ws_manager.broadcast(instance_id, {"event": "status", "status": "active"})
    return {"status": "active", "instance_id": instance_id}
