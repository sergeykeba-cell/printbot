"""
album.py — AlbumMiddleware для обробки media groups.

Кешує повідомлення з однаковим media_group_id протягом 0.5с,
потім передає їх разом як список. Ліміт — 5 файлів.
"""

import asyncio
from typing import Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

ALBUM_TIMEOUT = 0.5   # секунди очікування решти фото з альбому
MAX_FILES = 5


class AlbumMiddleware(BaseMiddleware):
    def __init__(self):
        self._albums: dict[str, list[Message]] = {}
        self._tasks: dict[str, asyncio.TimerHandle] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        # Якщо повідомлення не частина альбому — передаємо далі без змін
        if not event.media_group_id:
            return await handler(event, data)

        group_id = event.media_group_id

        # Додаємо до кешу
        if group_id not in self._albums:
            self._albums[group_id] = []

        if len(self._albums[group_id]) < MAX_FILES:
            self._albums[group_id].append(event)
        else:
            # Ліміт перевищено — повідомляємо і ігноруємо
            if len(self._albums[group_id]) == MAX_FILES:
                await event.answer(
                    f"⚠️ Максимум {MAX_FILES} файлів одночасно. "
                    "Решта файлів проігноровані."
                )
            return  # не обробляємо зайві файли

        # Скасовуємо попередній таймер якщо є
        if group_id in self._tasks:
            self._tasks[group_id].cancel()

        # Запускаємо новий таймер — через 0.5с передаємо альбом в хендлер
        loop = asyncio.get_event_loop()
        handle = loop.call_later(
            ALBUM_TIMEOUT,
            lambda: asyncio.ensure_future(
                self._flush_album(group_id, handler, data)
            ),
        )
        self._tasks[group_id] = handle

    async def _flush_album(
        self,
        group_id: str,
        handler: Callable,
        data: dict[str, Any],
    ) -> None:
        """Передає зібраний альбом у хендлер першого повідомлення."""
        messages = self._albums.pop(group_id, [])
        self._tasks.pop(group_id, None)

        if not messages:
            return

        # Передаємо список повідомлень через data["album"]
        first = messages[0]
        data["album"] = messages
        await handler(first, data)
