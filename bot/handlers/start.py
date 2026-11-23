"""/start, /menu, /cancel and the «🏠 В головне меню» button."""
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.callbacks import MenuCb
from bot.context import AppContext
from bot.handlers.helpers import drop_reply_keyboard_if_needed, show_main_menu

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, ctx: AppContext) -> None:
    user = message.from_user
    if user is None:
        return
    await drop_reply_keyboard_if_needed(message, state)
    await ctx.users.upsert(user.id, user.full_name, user.username)  # also un-blocks returning users
    await show_main_menu(message, state, ctx)


@router.message(Command("menu", "cancel"))
async def cmd_menu(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await drop_reply_keyboard_if_needed(message, state)
    await show_main_menu(message, state, ctx)


@router.message(Command("admin"))
async def cmd_admin_denied(message: Message) -> None:
    """Admins are handled by the admin router, which is included before this one."""
    await message.answer(texts.ACCESS_DENIED)


@router.callback_query(MenuCb.filter(F.action == "main"))
async def cb_main_menu(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await cb.answer()
    await show_main_menu(cb, state, ctx)
