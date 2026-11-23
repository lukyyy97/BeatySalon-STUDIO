"""Admin: close a whole day / period / time range for a master (vacation, sick leave...)."""
import datetime as dt
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.callbacks import AdmMenuCb, AdmOffCb
from bot.context import AppContext
from bot.filters import TEXT_INPUT
from bot.handlers.helpers import Target, edit_or_send, render
from bot.keyboards.admin import (
    timeoff_add_kb,
    timeoff_done_kb,
    timeoff_list_kb,
    timeoff_masters_kb,
    timeoff_scope_kb,
)
from bot.keyboards.common import back_kb
from bot.states import AdminTimeOffStates
from bot.utils.dates import find_dates, format_date_short, format_minutes, parse_iso_date
from bot.utils.validators import parse_time_range

logger = logging.getLogger(__name__)
router = Router(name="admin_timeoff")
S = AdminTimeOffStates

_MAX_RANGE_DAYS = 90
_DATE_PROMPT = (
    "➕ Введіть дату або період, коли майстер недоступний:\n\n"
    "• одна дата — <code>25.12.2026</code>\n"
    "• період — <code>25.12.2026-31.12.2026</code>\n\n"
    "Або скористайтеся кнопками нижче."
)


async def _show_list(target: Target, ctx: AppContext, master_id: int) -> None:
    master = await ctx.catalog.get_master(master_id)
    if master is None:
        await _show_masters(target, ctx)
        return
    items = await ctx.schedule.list_time_off(master_id, ctx.booking.today())
    await render(target, texts.timeoff_list(master, items), timeoff_list_kb(master_id, items))


async def _show_masters(target: Target, ctx: AppContext) -> None:
    masters = await ctx.catalog.list_masters(active_only=False)
    await render(
        target,
        "🚫 <b>Вихідні та закриття слотів</b>\n\nОберіть майстра:",
        timeoff_masters_kb(masters),
    )


async def _ask_scope(target: Target, state: FSMContext, master_id: int, day: dt.date) -> None:
    await state.set_state(S.scope)
    await state.update_data(off_master=master_id, off_date=day.isoformat())
    await render(
        target,
        f"📅 Дата: <b>{format_date_short(day)}</b>\n\nЗакрити весь день чи лише певні години?",
        timeoff_scope_kb(master_id),
    )


async def _close(
    target: Target,
    state: FSMContext,
    ctx: AppContext,
    master_id: int,
    first: dt.date,
    last: dt.date,
    start: int | None,
    end: int | None,
) -> None:
    master = await ctx.catalog.get_master(master_id)
    if master is None:
        await state.clear()
        await _show_masters(target, ctx)
        return

    days = [first + dt.timedelta(days=i) for i in range((last - first).days + 1)]
    for day in days:
        await ctx.schedule.add_time_off(master_id, day, start, end)

    conflicts = []
    for day in days:
        conflicts += await ctx.appointments.overlapping(
            master_id, day, start if start is not None else 0, end if end is not None else 24 * 60
        )
    await state.clear()

    period = format_date_short(first) if first == last else f"{format_date_short(first)} – {format_date_short(last)}"
    scope = "весь день" if start is None or end is None else f"{format_minutes(start)}–{format_minutes(end)}"
    text = (
        "✅ <b>Закрито для запису</b>\n\n"
        f"👩‍🎨 Майстер: <b>{texts.esc(master.name)}</b>\n"
        f"📅 Період: <b>{period}</b>\n"
        f"🕒 Час: <b>{scope}</b>"
    )
    if conflicts:
        lines = [
            f"• {format_date_short(a.date)} {format_minutes(a.start_min)} — {texts.esc(a.client_name)} ({texts.esc(a.service_name)})"
            for a in conflicts[:10]
        ]
        text += (
            f"\n\n⚠️ На цей час уже є активні записи ({len(conflicts)}):\n"
            + "\n".join(lines)
            + "\n\nСкасуйте їх у розкладі, якщо майстер не зможе прийняти клієнтів."
        )
    await render(target, text, timeoff_done_kb(master_id, first))


# --------------------------------------------------------------------------- list
@router.callback_query(AdmMenuCb.filter(F.action == "timeoff"))
async def menu_timeoff(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await cb.answer()
    await _show_masters(cb, ctx)


@router.callback_query(AdmOffCb.filter(F.action == "list"))
async def list_timeoff(cb: CallbackQuery, callback_data: AdmOffCb, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await cb.answer()
    await _show_list(cb, ctx, callback_data.m)


@router.callback_query(AdmOffCb.filter(F.action == "del"))
async def delete_timeoff(cb: CallbackQuery, callback_data: AdmOffCb, ctx: AppContext) -> None:
    await ctx.schedule.delete_time_off(callback_data.id)
    await cb.answer("Видалено")
    await _show_list(cb, ctx, callback_data.m)


# ---------------------------------------------------------------------------- add
@router.callback_query(AdmOffCb.filter(F.action == "add"))
async def add_timeoff(cb: CallbackQuery, callback_data: AdmOffCb, state: FSMContext, ctx: AppContext) -> None:
    await cb.answer()
    await state.set_state(S.date)
    await state.update_data(off_master=callback_data.m)
    await edit_or_send(cb, _DATE_PROMPT, timeoff_add_kb(callback_data.m, ctx.booking.today()))


@router.callback_query(AdmOffCb.filter(F.action == "quick"))
async def quick_date(cb: CallbackQuery, callback_data: AdmOffCb, state: FSMContext) -> None:
    day = parse_iso_date(callback_data.v)
    if day is None:
        await cb.answer(texts.STALE_BUTTON, show_alert=True)
        return
    await cb.answer()
    await _ask_scope(cb, state, callback_data.m, day)


@router.message(StateFilter(S.date), TEXT_INPUT)
async def date_typed(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    master_id = data.get("off_master")
    today = ctx.booking.today()
    dates = find_dates(message.text or "", today)
    if not master_id or not dates or len(dates) > 2:
        await message.answer("⚠️ Не вдалося розпізнати дату. Приклад: <code>25.12.2026</code> або <code>25.12.2026-31.12.2026</code>.")
        return
    first, last = min(dates), max(dates)
    if first < today:
        await message.answer("⚠️ Ця дата вже минула. Вкажіть сьогоднішню або майбутню дату.")
        return
    if (last - first).days >= _MAX_RANGE_DAYS:
        await message.answer(f"⚠️ Максимальний період — {_MAX_RANGE_DAYS} днів.")
        return
    if first == last:
        await _ask_scope(message, state, master_id, first)
    else:
        await _close(message, state, ctx, master_id, first, last, None, None)


@router.callback_query(AdmOffCb.filter(F.action == "whole"), StateFilter(S.scope))
async def close_whole_day(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    day = parse_iso_date(data.get("off_date"))
    master_id = data.get("off_master")
    if day is None or not master_id:
        await cb.answer(texts.STALE_BUTTON, show_alert=True)
        return
    await cb.answer()
    await _close(cb, state, ctx, master_id, day, day, None, None)


@router.callback_query(AdmOffCb.filter(F.action == "hours"), StateFilter(S.scope))
async def ask_hours(cb: CallbackQuery, callback_data: AdmOffCb, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(S.hours)
    await edit_or_send(
        cb,
        "🕒 Введіть години, коли майстер недоступний, у форматі <code>13:00-15:00</code>:",
        back_kb(AdmOffCb(action="list", m=callback_data.m)),
    )


@router.message(StateFilter(S.hours), TEXT_INPUT)
async def hours_typed(message: Message, state: FSMContext, ctx: AppContext) -> None:
    parsed = parse_time_range(message.text or "")
    if parsed is None:
        await message.answer("⚠️ Не вдалося розпізнати години. Формат: <code>13:00-15:00</code>.")
        return
    data = await state.get_data()
    day = parse_iso_date(data.get("off_date"))
    master_id = data.get("off_master")
    if day is None or not master_id:
        await state.clear()
        await message.answer(texts.GENERIC_ERROR)
        return
    await _close(message, state, ctx, master_id, day, day, parsed[0], parsed[1])
