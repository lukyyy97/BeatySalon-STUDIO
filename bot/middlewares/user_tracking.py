"""Keeps the `users` table in sync with everybody who talks to the bot."""
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.database.repositories import UserRepo

logger = logging.getLogger(__name__)

_REFRESH_SECONDS = 600


class UserTrackingMiddleware(BaseMiddleware):
    def __init__(self, users: UserRepo) -> None:
        self._users = users
        self._cache: dict[int, tuple[str, str | None, float]] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is not None and not user.is_bot:
            cached = self._cache.get(user.id)
            now = time.monotonic()
            stale = (
                cached is None
                or cached[0] != user.full_name
                or cached[1] != user.username
                or now - cached[2] > _REFRESH_SECONDS
            )
            if stale:
                try:
                    await self._users.upsert(user.id, user.full_name, user.username)
                    self._cache[user.id] = (user.full_name, user.username, now)
                except Exception:
                    logger.exception("Cannot upsert user %s", user.id)
        return await handler(event, data)
