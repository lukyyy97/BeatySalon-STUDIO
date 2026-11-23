"""Global error handler: log everything, never leave the user without a reply."""
import logging

from aiogram import Router
from aiogram.types import ErrorEvent

from bot import texts

logger = logging.getLogger(__name__)
router = Router(name="errors")


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    logger.error("Unhandled error while processing an update", exc_info=event.exception)
    update = event.update
    try:
        if update.callback_query is not None:
            await update.callback_query.answer(texts.GENERIC_ERROR, show_alert=True)
        elif update.message is not None:
            await update.message.answer(texts.GENERIC_ERROR)
    except Exception:
        logger.debug("Could not notify the user about the error", exc_info=True)
    return True
