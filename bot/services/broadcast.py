"""Mass mailing to all bot users with delivery statistics."""
import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from bot.database.repositories import UserRepo
from bot.services.notifications import Notifier, SendStatus

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], Awaitable[None]]


@dataclass(slots=True)
class BroadcastStats:
    total: int = 0
    sent: int = 0
    blocked: int = 0
    failed: int = 0


class BroadcastService:
    # Telegram allows ~30 messages per second for bots; stay comfortably below.
    _DELAY_SECONDS = 0.05
    _PROGRESS_EVERY = 25

    def __init__(self, notifier: Notifier, users: UserRepo) -> None:
        self._notifier = notifier
        self._users = users
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def run(self, html_text: str, on_progress: ProgressCallback | None = None) -> BroadcastStats:
        if self._running:
            raise RuntimeError("A broadcast is already running")
        self._running = True
        try:
            recipients = await self._users.broadcast_ids()
            stats = BroadcastStats(total=len(recipients))
            for index, chat_id in enumerate(recipients, start=1):
                status = await self._notifier.send(chat_id, html_text)
                if status is SendStatus.OK:
                    stats.sent += 1
                elif status is SendStatus.BLOCKED:
                    stats.blocked += 1
                else:
                    stats.failed += 1
                if on_progress is not None and index % self._PROGRESS_EVERY == 0:
                    await self._safe_progress(on_progress, index, stats.total)
                await asyncio.sleep(self._DELAY_SECONDS)
            logger.info("Broadcast finished: %s", stats)
            return stats
        finally:
            self._running = False

    @staticmethod
    async def _safe_progress(callback: ProgressCallback, done: int, total: int) -> None:
        try:
            await callback(done, total)
        except Exception:  # progress display must never break the mailing
            logger.debug("Progress callback failed", exc_info=True)
