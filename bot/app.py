"""Application assembly and startup."""
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat

from bot.config import get_settings
from bot.context import AppContext, build_context
from bot.database.db import Database
from bot.database.seed import seed_if_empty
from bot.handlers.root import build_root_router
from bot.logging_setup import setup_logging
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.middlewares.user_tracking import UserTrackingMiddleware
from bot.scheduler.setup import create_scheduler

logger = logging.getLogger(__name__)

_USER_COMMANDS = [
    BotCommand(command="start", description="Головне меню"),
    BotCommand(command="cancel", description="Скасувати поточну дію"),
]


async def _setup_commands(bot: Bot, ctx: AppContext) -> None:
    await bot.set_my_commands(_USER_COMMANDS)
    admin_commands = [*_USER_COMMANDS, BotCommand(command="admin", description="Адмін-панель")]
    for admin_id in ctx.admin_ids:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except TelegramAPIError as exc:  # the admin has not opened the bot yet
            logger.warning("Cannot set admin commands for %s: %s", admin_id, exc)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    if not settings.admin_ids:
        logger.warning("ADMIN_IDS is empty: the admin panel is unavailable and nobody gets notifications")

    db = Database(settings.db_path)
    await db.init()
    await seed_if_empty(db)

    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    ctx = build_context(settings, db, bot)

    # MemoryStorage keeps FSM state in RAM: a restart only interrupts bookings that are in progress.
    # Saved appointments and reminders live in SQLite. Swap in RedisStorage if you need more.
    dp = Dispatcher(storage=MemoryStorage())
    dp["ctx"] = ctx
    dp.message.outer_middleware(ThrottlingMiddleware(0.4))
    dp.callback_query.outer_middleware(ThrottlingMiddleware(0.4))
    tracker = UserTrackingMiddleware(ctx.users)
    dp.message.outer_middleware(tracker)
    dp.callback_query.outer_middleware(tracker)
    dp.include_router(build_root_router())

    scheduler = create_scheduler(ctx)
    try:
        try:
            me = await bot.get_me()
        except TelegramUnauthorizedError:
            logger.critical("Telegram rejected BOT_TOKEN. Check the value in your .env file.")
            return
        await bot.delete_webhook(drop_pending_updates=False)
        await _setup_commands(bot, ctx)
        scheduler.start()
        logger.info("Bot @%s started (timezone %s)", me.username, settings.timezone)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        await ctx.tasks.shutdown()
        await bot.session.close()
        logger.info("Bot stopped")
