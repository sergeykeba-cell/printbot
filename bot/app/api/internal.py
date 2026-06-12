"""
internal.py — внутрішній ендпоінт конфігурації інстансу.
GET /api/v1/internal/config — повертає план, ліміти, бонуси.
"""
import os
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/internal", tags=["Internal"])


@router.get("/config")
async def get_instance_config():
    """
    Повертає конфігурацію поточного інстансу.
    У продакшні — читає з Manager DB або env.
    """
    return {
        "instance_id": os.environ.get("INSTANCE_ID", "unknown"),
        "subdomain":   os.environ.get("INSTANCE_SUBDOMAIN", "unknown"),
        "plan_tier":   os.environ.get("PLAN_TIER", "free"),
        "max_orders_per_month": int(os.environ.get("MAX_ORDERS_PER_MONTH", "30")),
        "bonus_orders": int(os.environ.get("BONUS_ORDERS", "0")),
    }
