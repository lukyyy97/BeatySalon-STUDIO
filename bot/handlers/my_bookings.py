"""«Мої записи»: list, details and cancellation by the client."""
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot import texts
from bot.callbacks import MenuCb, MyApptCb
from bot.context import AppContext
from bot.database.models import Appointment
from bot.handlers.helpers import edit_or_send
from bot.keyboards.client import (
    appointment_kb,
    cancel_confirm_kb,
    cancel_done_kb,
    my_bookings_kb,
    no_bookings_kb,
)
from bot.services.booking import AppointmentNotFoundError, AppointmentStateError

logger = logging.getLogger(__name__)
router = Router(name="my_bookings")


async def _show_list(cb: CallbackQuery, ctx: AppContext) -> None:
    appts = await ctx.appointments.upcoming_for_user(cb.from_user.id, ctx.booking.now())
    if not appts:
        await edit_or_send(cb, texts.no_bookings(), no_bookings_kb())
        return
    await edit_or_send(cb, texts.my_bookings_header(), my_bookings_kb(appts))


async def _load_own(cb: CallbackQuery, ctx: AppContext, appt_id: int) -> Appointment | None:
    """Fetch an active appointment of the current user; otherwise tell them and show the list."""
    appt = await ctx.appointments.get(appt_id)
    if appt is None or appt.user_tg_id != cb.from_user.id or not appt.is_active:
        await cb.answer(texts.cancel_not_found(), show_alert=True)
        await _show_list(cb, ctx)
        return None
    return appt


@router.callback_query(MenuCb.filter(F.action == "my"))
async def my_bookings(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await cb.answer()
    await _show_list(cb, ctx)


@router.callback_query(MyApptCb.filter(F.action == "view"))
async def view_booking(cb: CallbackQuery, callback_data: MyApptCb, ctx: AppContext) -> None:
    appt = await _load_own(cb, ctx, callback_data.id)
    if appt is None:
        return
    await cb.answer()
    await edit_or_send(cb, f"📌 <b>Запис №{appt.id}</b>\n\n{texts.appointment_card(appt)}", appointment_kb(appt.id))


@router.callback_query(MyApptCb.filter(F.action == "ask"))
async def ask_cancel(cb: CallbackQuery, callback_data: MyApptCb, ctx: AppContext) -> None:
    appt = await _load_own(cb, ctx, callback_data.id)
    if appt is None:
        return
    await cb.answer()
    await edit_or_send(cb, texts.cancel_ask(appt), cancel_confirm_kb(appt.id))


@router.callback_query(MyApptCb.filter(F.action == "yes"))
async def confirm_cancel(cb: CallbackQuery, callback_data: MyApptCb, ctx: AppContext) -> None:
    async with ctx.locks.get(cb.from_user.id):
        try:
            appt = await ctx.booking.cancel_appointment(
                callback_data.id, cancelled_by="client", user_tg_id=cb.from_user.id
            )
        except AppointmentNotFoundError:
            await cb.answer(texts.cancel_not_found(), show_alert=True)
            await _show_list(cb, ctx)
            return
        except AppointmentStateError as exc:
            message = texts.cancel_started() if exc.reason == "started" else texts.cancel_not_found()
            await cb.answer(message, show_alert=True)
            await _show_list(cb, ctx)
            return

    await cb.answer()
    await edit_or_send(cb, texts.cancel_done(), cancel_done_kb())
    ctx.notifier.notify_admins_bg(texts.admin_client_cancelled(appt))
