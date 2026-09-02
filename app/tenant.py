"""
tenant.py — Зчитує INSTANCE_SUBDOMAIN та TENANT_MODE,
валідує ім'я схеми та надає get_schema_name().

Змінні оточення:
  INSTANCE_SUBDOMAIN  — субдомен інстансу (напр. "my-shop")
  TENANT_MODE         — "shared" (за замовчуванням) або "dedicated"

Правила формування імені схеми:
  subdomain → "tenant_" + subdomain.replace("-", "_")
  "my-shop" → "tenant_my_shop"

Безпека:
  - Субдомен валідується regex на старті.
  - При невалідному значенні — SystemExit (застосунок не стартує).
  - Ім'я схеми ніколи не підставляється через f-string у SQL напряму;
    воно використовується лише через sqlalchemy.text з явним quote_identifier.
"""
import os
import re
import logging
import sys

logger = logging.getLogger("tenant")

# Дозволені символи субдомену: малі літери, цифри, дефіс; 3–63 символи
_SUBDOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$")

# ── Зчитуємо конфіг при імпорті модуля ────────────────────────────

TENANT_MODE: str = os.getenv("TENANT_MODE", "shared").lower()

if TENANT_MODE not in ("shared", "dedicated"):
    logger.critical(
        f"[tenant] TENANT_MODE має бути 'shared' або 'dedicated', отримано: {TENANT_MODE!r}"
    )
    sys.exit(1)

if TENANT_MODE == "shared":
    _subdomain = os.getenv("INSTANCE_SUBDOMAIN", "").strip().lower()

    if not _subdomain:
        logger.critical(
            "[tenant] INSTANCE_SUBDOMAIN не встановлено. "
            "Встановіть змінну оточення або переключіть TENANT_MODE=dedicated."
        )
        sys.exit(1)

    if not _SUBDOMAIN_RE.match(_subdomain):
        logger.critical(
            f"[tenant] Невалідний INSTANCE_SUBDOMAIN={_subdomain!r}. "
            "Дозволено: малі літери [a-z], цифри [0-9], дефіс [-]; "
            "мінімум 3 символи, максимум 63, без дефісу на початку/кінці."
        )
        sys.exit(1)

    # "my-shop" → "tenant_my_shop"
    _schema_name: str = "tenant_" + _subdomain.replace("-", "_")
    logger.info(f"[tenant] Tenant schema set to {_schema_name!r} (subdomain={_subdomain!r})")

else:
    # dedicated — схема public, жодних маніпуляцій із search_path
    _schema_name = "public"
    logger.info("[tenant] TENANT_MODE=dedicated — використовується схема 'public', search_path не змінюється.")


def get_schema_name() -> str:
    """
    Повертає ім'я схеми поточного тенанта.

    Returns:
        "tenant_<subdomain>" для shared-режиму,
        "public" для dedicated-режиму.
    """
    return _schema_name


def is_shared() -> bool:
    """True якщо TENANT_MODE=shared — search_path manipulation потрібна."""
    return TENANT_MODE == "shared"
