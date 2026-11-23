"""Simple per-user anti-flood protection."""
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    """Drops updates arriving faster than `interval` seconds from the same user."""

    def __init__(self, interval: float = 0.4) -> None:
        self._interval = interval
        self._last_seen: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        now = time.monotonic()
        if now - self._last_seen.get(user.id, 0.0) < self._interval:
            if isinstance(event, CallbackQuery):
                await event.answer()  # stop the button spinner silently
            return None

        self._last_seen[user.id] = now
        if len(self._last_seen) > 10_000:  # keep memory bounded
            self._last_seen = {k: v for k, v in self._last_seen.items() if now - v < 60}
        return await handler(event, data)
