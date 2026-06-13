"""
main.py — FastAPI застосунок бота точки печати.

Зміни відносно попередньої версії:
  - install_rate_limit_handlers(app) підключає slowapi limiter,
    SlowAPIMiddleware та 429 exception handler.
  - PlanEnforcementMiddleware залишається — обробляє 402 для Free-тарифу.
  - Порядок middleware важливий: SlowAPIMiddleware має бути першим
    (додається останнім через add_middleware LIFO).
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.router import router
from app.api.internal import router as internal_router
from app.middleware.plan_enforcement import PlanEnforcementMiddleware
from app.core.rate_limiter import install_rate_limit_handlers
from app.database import init_db, init_redis, close_redis


async def _load_seed_prices():
    """
    Якщо таблиця print_prices порожня і є seed-файл — імпортуємо.
    Виконується один раз при старті після міграцій.
    """
    import json
    from pathlib import Path
    from sqlalchemy import text
    from app.database import AsyncSessionLocal

    seed_path = Path("/app/seed/seed_prices.json")
    if not seed_path.exists():
        return

    async with AsyncSessionLocal() as db:
        count = await db.scalar(text("SELECT COUNT(*) FROM print_prices"))
        if count and count > 0:
            return
        try:
            data = json.loads(seed_path.read_text())
            prices = data.get("print_prices", [])
            currency = data.get("currency", "UAH")
            for item in prices:
                await db.execute(
                    text(
                        """
                        INSERT INTO print_prices
                            (paper_size, color_mode, duplex, paper_weight, price_per_page, currency)
                        VALUES
                            (:paper_size, :color_mode, :duplex, :paper_weight, :price_per_page, :currency)
                        ON CONFLICT DO NOTHING
                        """
                    ),
                    {
                        "paper_size": item.get("paper_size", "A4"),
                        "color_mode": item.get("color_mode", "bw"),
                        "duplex": item.get("duplex", False),
                        "paper_weight": item.get("paper_weight", "80g"),
                        "price_per_page": item.get("price_per_page", 0),
                        "currency": currency,
                    },
                )
            await db.commit()
            print(f"[seed] Імпортовано {len(prices)} позицій прайс-листа.")
        except Exception as e:
            print(f"[seed] Помилка імпорту прайсу: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_redis()
    await _load_seed_prices()
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

# ── Rate limiting (slowapi) — підключаємо першим ──────────────────
# install_rate_limit_handlers додає SlowAPIMiddleware через add_middleware.
# FastAPI/Starlette застосовує middleware у зворотному порядку додавання (LIFO),
# тому SlowAPIMiddleware (додана тут) спрацює ПЕРШОЮ при вхідному запиті.
install_rate_limit_handlers(app)

# ── Plan enforcement (Free-tier 402) ──────────────────────────────
app.add_middleware(PlanEnforcementMiddleware)

# ── Роутери ───────────────────────────────────────────────────────
app.include_router(router)
app.include_router(internal_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
