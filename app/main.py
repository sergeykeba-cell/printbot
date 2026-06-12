"""
main.py — FastAPI застосунок Менеджера інстансів.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.orchestrator import router, public_router
from app.manager_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # При старті — ініціалізуємо таблиці (dev). В prod використовуй Alembic.
    await init_db()
    yield


app = FastAPI(
    title="PrintBot Instance Manager",
    description="Оркестратор ізольованих інстансів точок печати",
    version="1.0.0",
    lifespan=lifespan,
    # Вимикаємо публічну документацію в продакшені
    docs_url="/docs" if __import__("os").getenv("ENV") != "production" else None,
    redoc_url=None,
)

app.include_router(router)
app.include_router(public_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
