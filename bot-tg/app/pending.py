"""
pending.py — Зберігання активних замовлень у Redis для надійного polling.
"""
import json
import os
import redis

_redis = redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/1"))
PENDING_KEY = "printbot:pending"


def register_pending(user_id: int, job_id: str) -> None:
    """Реєструє замовлення для фонового відстеження."""
    _redis.hset(PENDING_KEY, str(user_id), json.dumps({"job_id": job_id, "notified": False}))


def get_all_pending() -> dict:
    """Повертає всі активні замовлення."""
    raw = _redis.hgetall(PENDING_KEY)
    return {int(k): json.loads(v) for k, v in raw.items()}


def mark_notified(user_id: int) -> None:
    """Позначає замовлення як повідомлене."""
    data = _redis.hget(PENDING_KEY, str(user_id))
    if data:
        entry = json.loads(data)
        entry["notified"] = True
        _redis.hset(PENDING_KEY, str(user_id), json.dumps(entry))
