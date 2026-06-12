"""
worker.py — ARQ воркер для ізольованого деплою інстансів.

Зміни відносно оригіналу:
- Додано _wait_for_healthy(): перевірка що контейнери реально запустились
  перед виставленням статусу "active"
- Таймаут очікування: 60 секунд (12 × 5с)
"""

import json
import os
import stat
import subprocess
import asyncio
import traceback
import time

from arq.connections import RedisSettings
from sqlalchemy import select

from app.manager_db import AsyncSessionLocal
from app.models import InstanceRegistry
from app.security import decrypt_secret, encrypt_secret


# ── Синхронний блок: файлові та системні операції ─────────────────

def _secure_provisioning(subdomain: str, bot_token: str, db_password: str, price_list: dict | None = None) -> None:
    """
    Виконується в окремому потоці через asyncio.to_thread().
    Містить усі блокуючі виклики: файлова система + subprocess.
    """
    template_path = "/opt/printbot/infrastructure/templates/docker-compose.instance.yml"

    if not os.path.exists(template_path):
        raise FileNotFoundError(
            f"Критична помилка: шаблон не знайдено за шляхом {template_path}"
        )

    base_dir = f"/opt/printbot/instances/{subdomain}"
    os.makedirs(base_dir, exist_ok=True)

    import secrets as _secrets
    instance_api_key = _secrets.token_urlsafe(32)
    operator_secret = _secrets.token_urlsafe(16)

    # Записуємо seed прайс-листа (Варіант В)
    os.makedirs(f"{base_dir}/data", exist_ok=True)
    seed_dst = f"{base_dir}/data/seed_prices.json"
    if price_list is not None:
        # Прайс переданий при створенні інстансу — пріоритет
        import json as _json
        fd = os.open(seed_dst, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            _json.dump(price_list, f, ensure_ascii=False, indent=2)
    else:
        # Fallback — глобальний шаблон якщо є
        seed_src = "/opt/printbot/manager/seed_prices.json"
        if os.path.exists(seed_src):
            import shutil
            shutil.copy2(seed_src, seed_dst)
            os.chmod(seed_dst, 0o600)

    env_content = (
        f"SUBDOMAIN={subdomain}\n"
        f"TG_BOT_TOKEN={bot_token}\n"
        f"DB_PASSWORD={db_password}\n"
        f"INSTANCE_API_KEY={instance_api_key}\n"
        f"OPERATOR_SECRET={operator_secret}\n"
        f"SHOP_NAME={subdomain}\n"
    )
    env_path = f"{base_dir}/.env"

    fd = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(env_content)

    subprocess.run(
        ["cp", template_path, f"{base_dir}/docker-compose.yml"],
        check=True,
    )

    # Створюємо web_network якщо не існує (потрібна для Traefik)
    subprocess.run(
        ["docker", "network", "create", "web_network"],
        capture_output=True,
    )  # Ігноруємо помилку якщо мережа вже існує

    subprocess.run(
        ["docker", "compose", "-p", f"printbot_{subdomain}", "up", "-d"],
        cwd=base_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    return operator_secret


def _wait_for_healthy(subdomain: str, timeout: int = 60, interval: int = 5) -> None:
    """
    Блокуюча перевірка: чекає поки всі контейнери стеку стануть
    'running' або 'healthy' (якщо є healthcheck).

    Виконується в окремому потоці через asyncio.to_thread().
    Кидає RuntimeError якщо таймаут вичерпано.
    """
    project_dir = f"/opt/printbot/instances/{subdomain}"
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                "docker", "compose", "-p", f"printbot_{subdomain}",
                "ps", "--format", "json",
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            time.sleep(interval)
            continue

        try:
            # docker compose ps --format json:
            #   Compose >= 2.21 → NDJSON (один об'єкт на рядок)
            #   Compose < 2.21  → один JSON масив
            raw = result.stdout.strip()
            if raw.startswith("["):
                containers = json.loads(raw)
            else:
                containers = [json.loads(line) for line in raw.splitlines() if line.strip()]
        except json.JSONDecodeError:
            time.sleep(interval)
            continue

        if not containers:
            time.sleep(interval)
            continue

        # Перевіряємо стан кожного контейнера.
        # Health може бути: "healthy", "unhealthy", "starting", "" (немає healthcheck).
        # Якщо поле відсутнє — вважаємо що healthcheck не налаштовано ("").
        # "starting" → чекаємо далі; "unhealthy" → чекаємо (може відновитись).
        all_ok = all(
            c.get("State") == "running"
            and c.get("Health", "") in ("healthy", "")
            for c in containers
        )

        if all_ok:
            return  # Всі контейнери OK

        time.sleep(interval)

    raise RuntimeError(
        f"Таймаут {timeout}с: контейнери інстансу '{subdomain}' не стали healthy. "
        f"Перевірте: docker compose -p printbot_{subdomain} ps"
    )


# ── Асинхронна ARQ задача ──────────────────────────────────────────

async def deploy_instance(ctx: dict, instance_id: str, price_list: dict | None = None) -> None:
    """
    ARQ задача. Отримує лише instance_id, самостійно читає
    і дешифрує секрети з БД Менеджера.
    """
    try:
        # Сесія 1: читаємо та дешифруємо секрети
        async with AsyncSessionLocal() as db:
            instance = await db.scalar(
                select(InstanceRegistry).where(InstanceRegistry.id == instance_id)
            )
            if not instance:
                print(f"❌ Інстанс {instance_id} не знайдено у БД. Задача скасована.")
                return

            subdomain = instance.subdomain
            bot_token = decrypt_secret(instance.encrypted_tg_bot_token)
            db_password = decrypt_secret(instance.encrypted_db_password)

        # Блокуючий I/O у окремому потоці: деплой + очікування healthy
        operator_secret = await asyncio.to_thread(_secure_provisioning, subdomain, bot_token, db_password, price_list)
        await asyncio.to_thread(_wait_for_healthy, subdomain)

        # Сесія 2: оновлюємо статус на "active"
        async with AsyncSessionLocal() as db:
            instance = await db.scalar(
                select(InstanceRegistry).where(InstanceRegistry.id == instance_id)
            )
            if not instance:
                print(f"⚠️ Інстанс {instance_id} видалено під час деплою. Статус не оновлено.")
                return
            instance.status = "active"
            instance.error_log = None
            instance.encrypted_operator_secret = encrypt_secret(operator_secret)
            await db.commit()

        print(f"✅ Інстанс {subdomain!r} успішно розгорнуто і перевірено.")

    except Exception:
        error_trace = traceback.format_exc()
        print(f"❌ Deploy failed for instance_id={instance_id}:\n{error_trace}")

        async with AsyncSessionLocal() as db:
            instance = await db.scalar(
                select(InstanceRegistry).where(InstanceRegistry.id == instance_id)
            )
            if instance:
                instance.status = "failed"
                instance.error_log = error_trace
                await db.commit()


# ── Конфігурація ARQ воркера ───────────────────────────────────────

class WorkerSettings:
    functions = [deploy_instance]
    redis_settings = RedisSettings.from_dsn(os.environ["REDIS_URL"])
    max_jobs = 3
    job_timeout = 300
