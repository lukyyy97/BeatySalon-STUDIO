"""Admin: services, masters, master ↔ service links and weekly working hours."""
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.callbacks import AdmCatCb, AdmMenuCb
from bot.context import AppContext
from bot.filters import TEXT_INPUT
from bot.handlers.helpers import Target, edit_or_send, render
from bot.keyboards.admin import (
    admin_day_kb,
    admin_master_kb,
    admin_master_services_kb,
    admin_masters_kb,
    admin_service_kb,
    admin_services_kb,
    admin_week_kb,
)
from bot.keyboards.common import back_kb
from bot.states import AdminCatalogStates
from bot.utils.dates import WEEKDAYS_FULL
from bot.utils.validators import (
    clean_title,
    parse_duration,
    parse_price,
    parse_work_hours,
)

router = Router(name="admin_catalog")
S = AdminCatalogStates

_SERVICE_FIELDS = {1: "name", 2: "price", 3: "duration"}
_SERVICE_PROMPTS = {
    "name": "✏️ Введіть нову назву послуги:",
    "price": "💰 Введіть нову ціну в гривнях (ціле число):",
    "duration": "⏱ Введіть нову тривалість у хвилинах (від 5 до 720):",
}
_BAD_TITLE = "⚠️ Назва має містити від 2 до 60 символів. Спробуйте ще раз."
_BAD_PRICE = "⚠️ Введіть ціну цілим числом, наприклад <code>600</code>."
_BAD_DURATION = "⚠️ Введіть тривалість у хвилинах від 5 до 720, наприклад <code>60</code>."
_BAD_HOURS = (
    "⚠️ Не вдалося розпізнати години. Формат: <code>09:00-18:00</code> "
    "або з перервою <code>09:00-18:00 13:00-14:00</code>."
)


# ------------------------------------------------------------------------ screens
async def _show_services(target: Target, ctx: AppContext) -> None:
    services = await ctx.catalog.list_services(active_only=False)
    await render(target, texts.admin_services_list(services), admin_services_kb(services))


async def _show_service(target: Target, ctx: AppContext, service_id: int) -> None:
    service = await ctx.catalog.get_service(service_id)
    if service is None:
        await _show_services(target, ctx)
        return
    masters = await ctx.catalog.masters_for_service(service_id)
    await render(target, texts.service_card(service, masters), admin_service_kb(service))


async def _show_masters(target: Target, ctx: AppContext) -> None:
    masters = await ctx.catalog.list_masters(active_only=False)
    await render(target, texts.admin_masters_list(masters), admin_masters_kb(masters))


async def _show_master(target: Target, ctx: AppContext, master_id: int) -> None:
    master = await ctx.catalog.get_master(master_id)
    if master is None:
        await _show_masters(target, ctx)
        return
    linked = await ctx.catalog.master_service_ids(master_id)
    services = [s for s in await ctx.catalog.list_services(active_only=False) if s.id in linked]
    week = await ctx.schedule.get_week(master_id)
    await render(target, texts.master_card(master, services, week), admin_master_kb(master))


async def _show_master_services(target: Target, ctx: AppContext, master_id: int) -> None:
    master = await ctx.catalog.get_master(master_id)
    if master is None:
        await _show_masters(target, ctx)
        return
    services = await ctx.catalog.list_services(active_only=False)
    linked = await ctx.catalog.master_service_ids(master_id)
    await render(
        target,
        f"💇 <b>Послуги майстра {texts.esc(master.name)}</b>\n\nНатискайте, щоб додати або прибрати послугу:",
        admin_master_services_kb(master_id, services, linked),
    )


async def _show_week(target: Target, ctx: AppContext, master_id: int) -> None:
    master = await ctx.catalog.get_master(master_id)
    if master is None:
        await _show_masters(target, ctx)
        return
    week = await ctx.schedule.get_week(master_id)
    await render(
        target,
        f"🗓 <b>Графік: {texts.esc(master.name)}</b>\n\nОберіть день тижня, щоб змінити години роботи:",
        admin_week_kb(master_id, week),
    )


# ----------------------------------------------------------------------- services
@router.callback_query(AdmMenuCb.filter(F.action == "services"))
async def menu_services(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await cb.answer()
    await _show_services(cb, ctx)


@router.callback_query(AdmCatCb.filter(F.action == "svc"))
async def open_service(cb: CallbackQuery, callback_data: AdmCatCb, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await cb.answer()
    await _show_service(cb, ctx, callback_data.id)


@router.callback_query(AdmCatCb.filter(F.action == "svc_toggle"))
async def toggle_service(cb: CallbackQuery, callback_data: AdmCatCb, ctx: AppContext) -> None:
    service = await ctx.catalog.get_service(callback_data.id)
    if service is not None:
        await ctx.catalog.update_service(service.id, is_active=not service.is_active)
    await cb.answer("Готово")
    await _show_service(cb, ctx, callback_data.id)


@router.callback_query(AdmCatCb.filter(F.action == "svc_new"))
async def new_service(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(S.service_name)
    await edit_or_send(cb, "➕ Введіть назву нової послуги:", back_kb(AdmMenuCb(action="services")))


@router.message(StateFilter(S.service_name), TEXT_INPUT)
async def new_service_name(message: Message, state: FSMContext) -> None:
    title = clean_title(message.text or "")
    if title is None:
        await message.answer(_BAD_TITLE)
        return
    await state.update_data(new_name=title)
    await state.set_state(S.service_price)
    await message.answer(
        "💰 Введіть ціну в гривнях (ціле число):", reply_markup=back_kb(AdmMenuCb(action="services"))
    )


@router.message(StateFilter(S.service_price), TEXT_INPUT)
async def new_service_price(message: Message, state: FSMContext) -> None:
    price = parse_price(message.text or "")
    if price is None:
        await message.answer(_BAD_PRICE)
        return
    await state.update_data(new_price=price)
    await state.set_state(S.service_duration)
    await message.answer(
        "⏱ Введіть тривалість у хвилинах (від 5 до 720), наприклад <code>60</code>:",
        reply_markup=back_kb(AdmMenuCb(action="services")),
    )


@router.message(StateFilter(S.service_duration), TEXT_INPUT)
async def new_service_duration(message: Message, state: FSMContext, ctx: AppContext) -> None:
    duration = parse_duration(message.text or "")
    if duration is None:
        await message.answer(_BAD_DURATION)
        return
    data = await state.get_data()
    if not data.get("new_name") or data.get("new_price") is None:
        await state.clear()
        await message.answer(texts.GENERIC_ERROR)
        return
    service_id = await ctx.catalog.add_service(data["new_name"], data["new_price"], duration)
    await state.clear()
    await message.answer("✅ Послугу додано. Не забудьте призначити майстрів: «Майстри» → майстер → «Послуги».")
    await _show_service(message, ctx, service_id)


@router.callback_query(AdmCatCb.filter(F.action == "svc_edit"))
async def edit_service_field(cb: CallbackQuery, callback_data: AdmCatCb, state: FSMContext) -> None:
    field = _SERVICE_FIELDS.get(callback_data.extra)
    if field is None:
        await cb.answer(texts.STALE_BUTTON, show_alert=True)
        return
    await cb.answer()
    await state.set_state(S.edit_value)
    await state.update_data(edit_kind="service", edit_id=callback_data.id, edit_field=field)
    await edit_or_send(
        cb, _SERVICE_PROMPTS[field], back_kb(AdmCatCb(action="svc", id=callback_data.id))
    )


# ------------------------------------------------------------------------ masters
@router.callback_query(AdmMenuCb.filter(F.action == "masters"))
async def menu_masters(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await cb.answer()
    await _show_masters(cb, ctx)


@router.callback_query(AdmCatCb.filter(F.action == "mst"))
async def open_master(cb: CallbackQuery, callback_data: AdmCatCb, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await cb.answer()
    await _show_master(cb, ctx, callback_data.id)


@router.callback_query(AdmCatCb.filter(F.action == "mst_toggle"))
async def toggle_master(cb: CallbackQuery, callback_data: AdmCatCb, ctx: AppContext) -> None:
    master = await ctx.catalog.get_master(callback_data.id)
    if master is not None:
        await ctx.catalog.update_master(master.id, is_active=not master.is_active)
    await cb.answer("Готово")
    await _show_master(cb, ctx, callback_data.id)


@router.callback_query(AdmCatCb.filter(F.action == "mst_new"))
async def new_master(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(S.master_name)
    await edit_or_send(cb, "➕ Введіть ім’я нового майстра:", back_kb(AdmMenuCb(action="masters")))


@router.message(StateFilter(S.master_name), TEXT_INPUT)
async def new_master_name(message: Message, state: FSMContext, ctx: AppContext) -> None:
    name = clean_title(message.text or "")
    if name is None:
        await message.answer(_BAD_TITLE)
        return
    master_id = await ctx.catalog.add_master(name)
    await state.clear()
    await message.answer("✅ Майстра додано. Тепер призначте послуги та задайте графік роботи.")
    await _show_master(message, ctx, master_id)


@router.callback_query(AdmCatCb.filter(F.action == "mst_rename"))
async def rename_master(cb: CallbackQuery, callback_data: AdmCatCb, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(S.edit_value)
    await state.update_data(edit_kind="master", edit_id=callback_data.id, edit_field="name")
    await edit_or_send(
        cb, "✏️ Введіть нове ім’я майстра:", back_kb(AdmCatCb(action="mst", id=callback_data.id))
    )


# ------------------------------------------------- shared "type a new value" handler
@router.message(StateFilter(S.edit_value), TEXT_INPUT)
async def apply_edit(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    kind, item_id, field = data.get("edit_kind"), data.get("edit_id"), data.get("edit_field")
    if kind not in {"service", "master"} or not item_id:
        await state.clear()
        await message.answer(texts.GENERIC_ERROR)
        return

    text = message.text or ""
    if field == "name":
        title = clean_title(text)
        if title is None:
            await message.answer(_BAD_TITLE)
            return
        if kind == "service":
            await ctx.catalog.update_service(item_id, name=title)
        else:
            await ctx.catalog.update_master(item_id, name=title)
    elif kind == "service" and field == "price":
        price = parse_price(text)
        if price is None:
            await message.answer(_BAD_PRICE)
            return
        await ctx.catalog.update_service(item_id, price=price)
    elif kind == "service" and field == "duration":
        duration = parse_duration(text)
        if duration is None:
            await message.answer(_BAD_DURATION)
            return
        await ctx.catalog.update_service(item_id, duration_min=duration)
    else:
        await state.clear()
        await message.answer(texts.GENERIC_ERROR)
        return

    await state.clear()
    await message.answer("✅ Збережено.")
    if kind == "service":
        await _show_service(message, ctx, item_id)
    else:
        await _show_master(message, ctx, item_id)


# ------------------------------------------------------------- master ↔ services
@router.callback_query(AdmCatCb.filter(F.action == "mst_svcs"))
async def master_services(cb: CallbackQuery, callback_data: AdmCatCb, ctx: AppContext) -> None:
    await cb.answer()
    await _show_master_services(cb, ctx, callback_data.id)


@router.callback_query(AdmCatCb.filter(F.action == "mst_svc_t"))
async def toggle_master_service(cb: CallbackQuery, callback_data: AdmCatCb, ctx: AppContext) -> None:
    await ctx.catalog.toggle_master_service(callback_data.id, callback_data.extra)
    await cb.answer()
    await _show_master_services(cb, ctx, callback_data.id)


# ----------------------------------------------------------------- weekly schedule
@router.callback_query(AdmCatCb.filter(F.action == "mst_sched"))
async def master_schedule(cb: CallbackQuery, callback_data: AdmCatCb, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await cb.answer()
    await _show_week(cb, ctx, callback_data.id)


@router.callback_query(AdmCatCb.filter(F.action == "mst_day"))
async def master_day(cb: CallbackQuery, callback_data: AdmCatCb, ctx: AppContext) -> None:
    weekday = callback_data.extra
    master = await ctx.catalog.get_master(callback_data.id)
    if master is None or not 0 <= weekday <= 6:
        await cb.answer(texts.STALE_BUTTON, show_alert=True)
        return
    week = await ctx.schedule.get_week(master.id)
    current = week[weekday].describe() if weekday in week else "вихідний"
    await cb.answer()
    await edit_or_send(
        cb,
        f"🗓 <b>{WEEKDAYS_FULL[weekday]}</b> · {texts.esc(master.name)}\n\n"
        f"Поточний режим: <b>{current}</b>\n\n"
        "ℹ️ Уже створені записи при зміні графіка не скасовуються.",
        admin_day_kb(master.id, weekday),
    )


@router.callback_query(AdmCatCb.filter(F.action == "mst_day_off"))
async def master_day_off(cb: CallbackQuery, callback_data: AdmCatCb, ctx: AppContext) -> None:
    if 0 <= callback_data.extra <= 6:
        await ctx.schedule.clear_day(callback_data.id, callback_data.extra)
    await cb.answer("День зроблено вихідним")
    await _show_week(cb, ctx, callback_data.id)


@router.callback_query(AdmCatCb.filter(F.action == "mst_day_set"))
async def ask_day_hours(cb: CallbackQuery, callback_data: AdmCatCb, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(S.day_hours)
    await state.update_data(hours_master=callback_data.id, hours_weekday=callback_data.extra)
    await edit_or_send(
        cb,
        f"✏️ <b>{WEEKDAYS_FULL[callback_data.extra % 7]}</b>: введіть години роботи у форматі "
        "<code>09:00-18:00</code>.\nЗа потреби додайте перерву через пробіл: "
        "<code>09:00-18:00 13:00-14:00</code>.",
        back_kb(AdmCatCb(action="mst_day", id=callback_data.id, extra=callback_data.extra)),
    )


@router.message(StateFilter(S.day_hours), TEXT_INPUT)
async def set_day_hours(message: Message, state: FSMContext, ctx: AppContext) -> None:
    parsed = parse_work_hours(message.text or "")
    if parsed is None:
        await message.answer(_BAD_HOURS)
        return
    data = await state.get_data()
    master_id, weekday = data.get("hours_master"), data.get("hours_weekday")
    if not master_id or weekday is None:
        await state.clear()
        await message.answer(texts.GENERIC_ERROR)
        return
    start, end, break_start, break_end = parsed
    await ctx.schedule.set_day(master_id, weekday, start, end, break_start, break_end)
    await state.clear()
    await message.answer("✅ Графік збережено.")
    await _show_week(message, ctx, master_id)
