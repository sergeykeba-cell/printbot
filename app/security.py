"""
security.py — Автентифікація та шифрування секретів.

Правила:
- Жодних дефолтних значень для секретних змінних (os.environ["KEY"], не .get())
- Обидва секрети (tg_bot_token, db_password) шифруються через Fernet
"""

import os
from cryptography.fernet import Fernet
from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader

# ── Завантаження змінних оточення (падаємо при старті якщо немає) ──
MANAGER_API_KEY: str = os.environ["MANAGER_API_KEY"]
_ENCRYPTION_KEY: str = os.environ["ENCRYPTION_KEY"]  # Генерувати: Fernet.generate_key()

cipher_suite = Fernet(_ENCRYPTION_KEY.encode() if isinstance(_ENCRYPTION_KEY, str) else _ENCRYPTION_KEY)

# ── API Key автентифікація ──────────────────────────────────────────
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


async def verify_manager_access(api_key: str = Security(_api_key_header)) -> str:
    if api_key != MANAGER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ заборонено: невірний API токен",
        )
    return api_key


# ── Шифрування / дешифрування ──────────────────────────────────────
def encrypt_secret(value: str) -> str:
    """Шифрує рядок через Fernet. Повертає base64-рядок."""
    return cipher_suite.encrypt(value.encode()).decode()


def decrypt_secret(encrypted_value: str) -> str:
    """Дешифрує Fernet-рядок. Кидає InvalidToken при підробці."""
    return cipher_suite.decrypt(encrypted_value.encode()).decode()
