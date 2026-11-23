"""Reusable filters."""
from aiogram import F
from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from bot.context import AppContext

# Plain text that is not a command: used by every "type a value" FSM step.
TEXT_INPUT = F.text & ~F.text.startswith("/")


class IsAdmin(BaseFilter):
    """Passes only for users listed in ADMIN_IDS."""

    async def __call__(self, event: TelegramObject, ctx: AppContext) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and ctx.is_admin(user.id)
