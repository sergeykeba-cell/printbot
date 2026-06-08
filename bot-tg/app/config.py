"""
config.py — Конфігурація бота з змінних оточення.
"""

import os


class Settings:
    # Telegram bot token (з BotFather)
    BOT_TOKEN: str = os.environ["BOT_TOKEN"]

    # URL FastAPI інстансу (всередині Docker мережі)
    INSTANCE_API_URL: str = os.environ.get("INSTANCE_API_URL", "http://api:8000")

    # API ключ для доступу до FastAPI інстансу
    INSTANCE_API_KEY: str = os.environ["INSTANCE_API_KEY"]

    # Назва точки печати (для привітання)
    SHOP_NAME: str = os.environ.get("SHOP_NAME", "Точка печати")

    # Секретний код оператора
    OPERATOR_SECRET: str = os.environ.get("OPERATOR_SECRET", "")

    # Максимальний розмір файлу (50MB)
    INSTANCE_SUBDOMAIN: str = os.environ.get("INSTANCE_SUBDOMAIN", "test-shop")
    MAX_FILE_SIZE: int = 50 * 1024 * 1024


settings = Settings()
