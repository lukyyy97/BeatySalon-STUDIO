"""Catch-all handlers; must be included last."""
from aiogram import Router
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.context import AppContext
from bot.keyboards.client import main_menu_kb

router = Router(name="fallback")


@router.callback_query()
async def stale_callback(cb: CallbackQuery) -> None:
    await cb.answer(texts.STALE_BUTTON, show_alert=True)


@router.message()
async def unknown_message(message: Message, ctx: AppContext) -> None:
    user = message.from_user
    is_admin = user is not None and ctx.is_admin(user.id)
    await message.answer(texts.NOT_UNDERSTOOD, reply_markup=main_menu_kb(is_admin))
