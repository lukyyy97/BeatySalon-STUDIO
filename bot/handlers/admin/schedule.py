"""Admin: schedule by day / master, appointment cards, cancellation."""
import datetime as dt

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.callbacks import AdmApptCb, AdmMenuCb, AdmSchedCb
from bot.context import AppContext
from bot.filters import TEXT_INPUT
from bot.handlers.helpers import Target, edit_or_send, render
from bot.keyboards.admin import (
    admin_after_cancel_kb,
    admin_appt_kb,
    admin_cancel_confirm_kb,
    schedule_kb,
)
from bot.keyboards.common import back_kb
from bot.services.booking import AppointmentNotFoundError, AppointmentStateError
from bot.services.notifications import SendStatus
from bot.states import AdminScheduleStates
from bot.utils.dates import find_dates, parse_iso_date

router = Router(name="admin_schedule")


async def show_schedule(target: Target, ctx: AppContext, day: dt.date, master_id: int = 0) -> None:
    masters = await ctx.catalog.list_masters(active_only=False)
    master = next((m for m in masters if m.id == master_id), None)
    appts = await ctx.appointments.for_day(day, master.id if master else None)
    await render(
        target,
        texts.admin_schedule(day, appts, master.name if master else None),
        schedule_kb(appts, day, master.id if master else 0, masters, ctx.booking.today()),
    )


@router.callback_query(AdmMenuCb.filter(F.action == "schedule"))
async def open_schedule(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await cb.answer()
    await show_schedule(cb, ctx, ctx.booking.today())


@router.callback_query(AdmSchedCb.filter())
async def schedule_navigate(
    cb: CallbackQuery, callback_data: AdmSchedCb, state: FSMContext, ctx: AppContext
) -> None:
    await state.clear()
    await cb.answer()
    day = parse_iso_date(callback_data.d) or ctx.booking.today()
    await show_schedule(cb, ctx, day, callback_data.m)


@router.callback_query(AdmMenuCb.filter(F.action == "sched_date"))
async def ask_schedule_date(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(AdminScheduleStates.wait_date)
    await edit_or_send(
        cb,
        "📆 Введіть дату у форматі <code>ДД.ММ.РРРР</code>, наприклад <code>25.11.2026</code>:",
        back_kb(AdmMenuCb(action="schedule")),
    )


@router.message(StateFilter(AdminScheduleStates.wait_date), TEXT_INPUT)
async def got_schedule_date(message: Message, state: FSMContext, ctx: AppContext) -> None:
    dates = find_dates(message.text or "", ctx.booking.today())
    if not dates or len(dates) != 1:
        await message.answer("⚠️ Не вдалося розпізнати дату. Введіть її у форматі <code>ДД.ММ.РРРР</code>.")
        return
    await state.clear()
    await show_schedule(message, ctx, dates[0])


# ------------------------------------------------------------------ appointment card
@router.callback_query(AdmApptCb.filter(F.action == "view"))
async def view_appointment(cb: CallbackQuery, callback_data: AdmApptCb, ctx: AppContext) -> None:
    appt = await ctx.appointments.get(callback_data.id)
    if appt is None:
        await cb.answer(texts.cancel_not_found(), show_alert=True)
        return
    await cb.answer()
    await edit_or_send(cb, texts.admin_appt_card(appt), admin_appt_kb(appt))


@router.callback_query(AdmApptCb.filter(F.action == "ask"))
async def ask_cancel(cb: CallbackQuery, callback_data: AdmApptCb, ctx: AppContext) -> None:
    appt = await ctx.appointments.get(callback_data.id)
    if appt is None or not appt.is_active:
        await cb.answer(texts.cancel_not_found(), show_alert=True)
        return
    await cb.answer()
    await edit_or_send(cb, texts.admin_cancel_ask(appt), admin_cancel_confirm_kb(appt.id))


@router.callback_query(AdmApptCb.filter(F.action == "yes"))
async def confirm_cancel(cb: CallbackQuery, callback_data: AdmApptCb, ctx: AppContext) -> None:
    try:
        appt = await ctx.booking.cancel_appointment(
            callback_data.id, cancelled_by="admin", allow_started=True
        )
    except (AppointmentNotFoundError, AppointmentStateError):
        await cb.answer(texts.cancel_not_found(), show_alert=True)
        return

    notified = False
    if appt.user_tg_id is not None:
        status = await ctx.notifier.send(appt.user_tg_id, texts.client_cancelled_by_admin(appt))
        notified = status is SendStatus.OK
    await cb.answer()
    await edit_or_send(cb, texts.admin_cancel_done(appt, notified), admin_after_cancel_kb(appt.date))
