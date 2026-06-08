"""
main.py — FastAPI застосунок бота точки печати.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.router import router
from app.database import init_db, init_redis, close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_redis()
    yield
    await close_redis()


app = FastAPI(
    title="PrintBot Instance",
    description="API точки печати",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if os.getenv("ENV") != "production" else None,
    redoc_url=None,
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
