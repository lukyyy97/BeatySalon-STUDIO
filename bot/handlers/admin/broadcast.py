"""Admin: mass mailing with preview and delivery statistics."""
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.callbacks import AdmMenuCb, BroadcastCb
from bot.context import AppContext
from bot.filters import TEXT_INPUT
from bot.handlers.admin.views import show_admin_menu
from bot.handlers.helpers import edit_or_send
from bot.keyboards.admin import broadcast_confirm_kb
from bot.keyboards.common import back_kb
from bot.states import AdminBroadcastStates

logger = logging.getLogger(__name__)
router = Router(name="admin_broadcast")
S = AdminBroadcastStates

_MAX_LENGTH = 3500
_PROMPT = (
    "📣 <b>Розсилка</b>\n\n"
    "Надішліть текст повідомлення, яке отримають усі користувачі бота. "
    "Підтримується форматування Telegram: жирний, курсив, посилання."
)


async def _ask_text(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(S.text)
    await edit_or_send(cb, _PROMPT, back_kb(AdmMenuCb(action="main")))


@router.callback_query(AdmMenuCb.filter(F.action == "broadcast"))
async def start_broadcast(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await _ask_text(cb, state)


@router.message(StateFilter(S.text), TEXT_INPUT)
async def got_text(message: Message, state: FSMContext, ctx: AppContext) -> None:
    html_text = message.html_text
    if len(message.text or "") > _MAX_LENGTH:
        await message.answer(f"⚠️ Повідомлення завелике. Максимум — {_MAX_LENGTH} символів.")
        return
    try:  # preview: exactly what the users will receive
        await message.answer(html_text)
    except TelegramBadRequest:
        await message.answer("⚠️ Telegram не зміг показати це повідомлення. Перевірте форматування та спробуйте ще раз.")
        return
    recipients = len(await ctx.users.broadcast_ids())
    await state.update_data(html=html_text)
    await state.set_state(S.confirm)
    await message.answer(texts.broadcast_confirm(recipients), reply_markup=broadcast_confirm_kb())


@router.callback_query(BroadcastCb.filter(F.action == "edit"), StateFilter(S.confirm))
async def edit_text(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await _ask_text(cb, state)


@router.callback_query(BroadcastCb.filter(F.action == "cancel"))
async def cancel_broadcast(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await cb.answer("Розсилку скасовано")
    await show_admin_menu(cb, ctx)


async def _set_status(cb: CallbackQuery, text: str) -> None:
    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_text(text)
        except TelegramAPIError:
            logger.debug("Could not update the broadcast status message", exc_info=True)


@router.callback_query(BroadcastCb.filter(F.action == "send"), StateFilter(S.confirm))
async def send_broadcast(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    html_text = data.get("html")
    if not html_text:
        await cb.answer(texts.STALE_BUTTON, show_alert=True)
        return
    if ctx.broadcaster.is_running:
        await cb.answer("Інша розсилка ще виконується. Зачекайте її завершення.", show_alert=True)
        return

    await state.clear()
    await cb.answer("Розсилку запущено")
    await _set_status(cb, "⏳ Розсилку розпочато…")
    admin_id = cb.from_user.id

    async def on_progress(done: int, total: int) -> None:
        await _set_status(cb, f"⏳ Розсилка триває: {done} з {total}")

    async def job() -> None:
        stats = await ctx.broadcaster.run(html_text, on_progress)
        await _set_status(cb, "✅ Розсилку завершено.")
        await ctx.notifier.send(
            admin_id,
            texts.broadcast_report(stats.total, stats.sent, stats.blocked, stats.failed),
            reply_markup=back_kb(AdmMenuCb(action="main")),
            mark_blocked=False,
        )

    ctx.tasks.spawn(job(), name="broadcast")
