"""Small helpers shared by handlers."""
import logging

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from bot import texts
from bot.context import AppContext
from bot.keyboards.client import main_menu_kb
from bot.states import BookingStates

logger = logging.getLogger(__name__)

Target = Message | CallbackQuery
Markup = InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | None


def user_id_of(target: Target) -> int:
    user = target.from_user
    if user is None:
        raise ValueError("Update has no sender")
    return user.id


async def edit_or_send(cb: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """Edit the message under the pressed button; fall back to a new message if that is impossible."""
    message = cb.message
    if isinstance(message, Message):
        try:
            await message.edit_text(text, reply_markup=reply_markup)
            return
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return
            logger.debug("Cannot edit message, sending a new one: %s", exc)
    await cb.bot.send_message(cb.from_user.id, text, reply_markup=reply_markup)


async def send_new(target: Target, text: str, reply_markup: Markup = None) -> None:
    """Always send a brand-new message to the user's chat."""
    if isinstance(target, CallbackQuery):
        await target.bot.send_message(target.from_user.id, text, reply_markup=reply_markup)
    else:
        await target.answer(text, reply_markup=reply_markup)


async def render(target: Target, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """Callbacks edit the current message, plain messages get a new reply."""
    if isinstance(target, CallbackQuery):
        await edit_or_send(target, text, reply_markup)
    else:
        await target.answer(text, reply_markup=reply_markup)


async def remove_reply_keyboard(message: Message) -> None:
    """Remove the reply keyboard (Telegram needs a message to do that) without leaving a trace."""
    try:
        helper = await message.answer("⏳", reply_markup=ReplyKeyboardRemove())
        await helper.delete()
    except TelegramAPIError:
        logger.debug("Could not remove the reply keyboard", exc_info=True)


async def show_main_menu(target: Target, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    user = target.from_user
    if user is None:
        return
    await render(
        target,
        texts.welcome(ctx.settings.salon_name, user.first_name),
        main_menu_kb(ctx.is_admin(user.id)),
    )


async def drop_reply_keyboard_if_needed(message: Message, state: FSMContext) -> None:
    """Commands typed on the phone step must not leave the contact keyboard on screen."""
    if await state.get_state() == BookingStates.phone.state:
        await remove_reply_keyboard(message)
