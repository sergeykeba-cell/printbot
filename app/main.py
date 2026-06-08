"""
main.py — FastAPI застосунок Менеджера інстансів.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.orchestrator import router
from app.manager_db import init_db, init_redis, close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_redis()
    yield
    await close_redis()


app = FastAPI(
    title="PrintBot Instance Manager",
    description="Оркестратор ізольованих інстансів точок печати",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if __import__("os").getenv("ENV") != "production" else None,
    redoc_url=None,
)

app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
