"""Safe message delivery: retries on flood limits, detects blocked users."""
import asyncio
import enum
import logging
from collections.abc import Iterable

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from aiogram.types import InlineKeyboardMarkup

from bot.database.repositories import UserRepo
from bot.utils.tasks import BackgroundTasks

logger = logging.getLogger(__name__)


class SendStatus(enum.Enum):
    OK = "ok"
    BLOCKED = "blocked"  # the user blocked the bot / deleted the account
    FAILED = "failed"  # transient or unknown error


class Notifier:
    def __init__(
        self, bot: Bot, users: UserRepo, admin_ids: Iterable[int], tasks: BackgroundTasks
    ) -> None:
        self._bot = bot
        self._users = users
        self._admin_ids = tuple(admin_ids)
        self._tasks = tasks

    async def send(
        self,
        chat_id: int,
        text: str,
        *,
        reply_markup: InlineKeyboardMarkup | None = None,
        mark_blocked: bool = True,
    ) -> SendStatus:
        for attempt in range(1, 4):
            try:
                await self._bot.send_message(chat_id, text, reply_markup=reply_markup)
                return SendStatus.OK
            except TelegramRetryAfter as exc:
                logger.warning("Flood limit hit, sleeping %ss", exc.retry_after)
                await asyncio.sleep(exc.retry_after + 0.5)
            except TelegramForbiddenError:
                if mark_blocked:
                    await self._users.mark_blocked(chat_id)
                logger.info("Chat %s is not reachable (blocked/deactivated)", chat_id)
                return SendStatus.BLOCKED
            except TelegramBadRequest as exc:
                if "chat not found" in str(exc).lower():
                    if mark_blocked:
                        await self._users.mark_blocked(chat_id)
                    return SendStatus.BLOCKED
                logger.warning("Cannot send message to %s: %s", chat_id, exc)
                return SendStatus.FAILED
            except (TelegramNetworkError, TelegramAPIError) as exc:
                logger.warning("Send to %s failed (attempt %s/3): %s", chat_id, attempt, exc)
                await asyncio.sleep(attempt)
        return SendStatus.FAILED

    async def notify_admins(self, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
        if not self._admin_ids:
            logger.warning("ADMIN_IDS is empty: nobody to notify")
            return
        await asyncio.gather(
            *(self.send(admin_id, text, reply_markup=reply_markup, mark_blocked=False) for admin_id in self._admin_ids)
        )

    def notify_admins_bg(self, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
        """Notify admins without making the current handler wait."""
        self._tasks.spawn(self.notify_admins(text, reply_markup), name="notify_admins")
