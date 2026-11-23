"""Step-by-step booking flow shared by clients and by the admin («➕ Додати запис»).

`build_flow_router(spec)` returns a router with all handlers of the flow bound to the state
group from `spec`, so the client and the admin flows reuse exactly the same code.
"""
import logging
from dataclasses import dataclass
from typing import Any

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message

from bot import texts
from bot.callbacks import (
    AdmMenuCb,
    ConfirmCb,
    DateCb,
    FlowNavCb,
    MasterCb,
    MenuCb,
    ServiceCb,
    StepCb,
    TimeCb,
)
from bot.context import AppContext
from bot.filters import TEXT_INPUT
from bot.handlers.helpers import (
    Target,
    edit_or_send,
    remove_reply_keyboard,
    render,
    send_new,
    show_main_menu,
    user_id_of,
)
from bot.keyboards.admin import admin_after_create_kb
from bot.keyboards.booking import (
    after_booking_kb,
    confirm_kb,
    dates_kb,
    masters_kb,
    name_kb,
    phone_request_kb,
    phone_skip_kb,
    services_kb,
    times_kb,
)
from bot.keyboards.common import BTN_BACK, BTN_HOME, MENU_MAIN, markup, nav_row
from bot.services.booking import SlotUnavailableError
from bot.states import AdminAddStates, BookingStates
from bot.utils.dates import parse_iso_date
from bot.utils.validators import normalize_contact_phone, normalize_phone, validate_name

logger = logging.getLogger(__name__)

_STEPS = ("service", "master", "date", "time", "name", "phone", "confirm")
_BACK_OF = {
    "master": "service",
    "date": "master",
    "time": "date",
    "name": "time",
    "phone": "name",
    "confirm": "phone",
}


@dataclass(frozen=True, slots=True)
class FlowSpec:
    name: str
    scope: str  # "c" (client) or "a" (admin): part of the «back» callback data
    states: type[StatesGroup]
    exit_cb: str  # packed callback of «⬅️ Назад» on the first step
    by_admin: bool = False


CLIENT_FLOW = FlowSpec(
    name="client_booking",
    scope="c",
    states=BookingStates,
    exit_cb=MENU_MAIN,
)
ADMIN_FLOW = FlowSpec(
    name="admin_booking",
    scope="a",
    states=AdminAddStates,
    exit_cb=AdmMenuCb(action="main").pack(),
    by_admin=True,
)


def _state(spec: FlowSpec, step: str) -> State:
    state = getattr(spec.states, step)
    assert isinstance(state, State)
    return state


def _nav(spec: FlowSpec, step: str) -> list[InlineKeyboardButton]:
    back = spec.exit_cb if step == "service" else FlowNavCb(scope=spec.scope, to=_BACK_OF[step]).pack()
    return nav_row(back, MENU_MAIN)


async def _master_label(ctx: AppContext, data: dict[str, Any]) -> str:
    master_id = data.get("master_id")
    if not master_id:
        return texts.ANY_MASTER
    master = await ctx.catalog.get_master(master_id)
    return master.name if master else texts.ANY_MASTER


# --------------------------------------------------------------------------- steps
async def show_services(
    target: Target, state: FSMContext, ctx: AppContext, spec: FlowSpec, notice: str = ""
) -> None:
    services = await ctx.catalog.list_services()
    await state.set_state(_state(spec, "service"))
    if not services:
        await render(target, notice + texts.no_services(), markup(_nav(spec, "service")))
        return
    await render(target, notice + texts.step_service(), services_kb(services, _nav(spec, "service")))


async def show_masters(
    target: Target, state: FSMContext, ctx: AppContext, spec: FlowSpec, notice: str = ""
) -> None:
    data = await state.get_data()
    service = await ctx.catalog.get_service(data["service_id"]) if data.get("service_id") else None
    if service is None or not service.is_active:
        await show_services(target, state, ctx, spec, notice=texts.service_unavailable() + "\n\n")
        return
    masters = await ctx.catalog.masters_for_service(service.id)
    await state.set_state(_state(spec, "master"))
    if not masters:
        await render(target, texts.no_masters(service.name), markup(_nav(spec, "master")))
        return
    await render(target, notice + texts.step_master(service), masters_kb(masters, _nav(spec, "master")))


async def show_dates(
    target: Target, state: FSMContext, ctx: AppContext, spec: FlowSpec, notice: str = ""
) -> None:
    data = await state.get_data()
    service = await ctx.catalog.get_service(data["service_id"]) if data.get("service_id") else None
    if service is None or data.get("master_id") is None:
        await show_services(target, state, ctx, spec)
        return
    dates = await ctx.booking.available_dates(service.id, data["master_id"], admin=spec.by_admin)
    await state.set_state(_state(spec, "date"))
    if not dates:
        await render(
            target,
            notice + texts.no_dates(ctx.settings.booking_horizon_days),
            markup(_nav(spec, "date")),
        )
        return
    label = await _master_label(ctx, data)
    await render(target, notice + texts.step_date(service, label), dates_kb(dates, _nav(spec, "date")))


async def show_times(
    target: Target, state: FSMContext, ctx: AppContext, spec: FlowSpec, notice: str = ""
) -> None:
    data = await state.get_data()
    service = await ctx.catalog.get_service(data["service_id"]) if data.get("service_id") else None
    day = parse_iso_date(data.get("date"))
    if service is None or data.get("master_id") is None or day is None:
        await show_services(target, state, ctx, spec)
        return
    slots = await ctx.booking.free_slots(service.id, data["master_id"], day, admin=spec.by_admin)
    if not slots:
        await show_dates(target, state, ctx, spec, notice=texts.no_slots_for_date() + "\n\n")
        return
    await state.set_state(_state(spec, "time"))
    label = await _master_label(ctx, data)
    await render(
        target, notice + texts.step_time(service, label, day), times_kb(slots, _nav(spec, "time"))
    )


async def show_name(target: Target, state: FSMContext, ctx: AppContext, spec: FlowSpec) -> None:
    data = await state.get_data()
    suggested = None if spec.by_admin else data.get("suggested_name")
    await state.set_state(_state(spec, "name"))
    await render(
        target,
        texts.step_name(suggested, by_admin=spec.by_admin),
        name_kb(suggested, _nav(spec, "name")),
    )


async def show_phone(target: Target, state: FSMContext, ctx: AppContext, spec: FlowSpec) -> None:
    data = await state.get_data()
    await state.set_state(_state(spec, "phone"))
    if spec.by_admin:
        await render(target, texts.step_phone(by_admin=True), phone_skip_kb(_nav(spec, "phone")))
        return
    if isinstance(target, CallbackQuery):
        # Freeze the name prompt (drops its inline buttons); the reply keyboard needs a new message.
        await edit_or_send(target, texts.name_saved(data.get("client_name", "")))
    user = await ctx.users.get(user_id_of(target))
    saved_phone = user.phone if user else None
    await send_new(target, texts.step_phone(by_admin=False), phone_request_kb(saved_phone))


async def show_confirm(
    target: Target,
    state: FSMContext,
    ctx: AppContext,
    spec: FlowSpec,
    *,
    remove_reply_kb: bool = False,
) -> None:
    data = await state.get_data()
    service = await ctx.catalog.get_service(data["service_id"]) if data.get("service_id") else None
    master = await ctx.catalog.get_master(data["assigned_master_id"]) if data.get("assigned_master_id") else None
    day = parse_iso_date(data.get("date"))
    if service is None or master is None or day is None or data.get("minute") is None:
        await show_services(target, state, ctx, spec)
        return
    if remove_reply_kb and isinstance(target, Message):
        await remove_reply_keyboard(target)
    await state.set_state(_state(spec, "confirm"))
    summary = texts.booking_summary(
        service,
        master.name,
        bool(data.get("any_master")),
        day,
        data["minute"],
        data.get("client_name", ""),
        data.get("client_phone", ""),
    )
    yes_text = "✅ Створити запис" if spec.by_admin else "✅ Підтвердити запис"
    await render(target, summary, confirm_kb(_nav(spec, "confirm"), yes_text))


_RENDERERS = {
    "service": show_services,
    "master": show_masters,
    "date": show_dates,
    "time": show_times,
    "name": show_name,
    "phone": show_phone,
}


async def start_flow(target: Target, state: FSMContext, ctx: AppContext, spec: FlowSpec) -> None:
    """Begin a fresh booking (drops any previous FSM data)."""
    await state.clear()
    await show_services(target, state, ctx, spec)


# ------------------------------------------------------------------------- router
def build_flow_router(spec: FlowSpec) -> Router:
    router = Router(name=spec.name)
    st_confirm = _state(spec, "confirm")
    all_steps = StateFilter(*(_state(spec, step) for step in _STEPS))

    # ---- entry point of the client flow (the admin flow starts from the admin panel) ----
    if not spec.by_admin:

        @router.callback_query(MenuCb.filter(F.action == "book"))
        async def begin(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
            await cb.answer()
            await start_flow(cb, state, ctx, spec)

    # ---- «⬅️ Назад» (inline) ----
    @router.callback_query(FlowNavCb.filter(F.scope == spec.scope), all_steps)
    async def go_back(cb: CallbackQuery, callback_data: FlowNavCb, state: FSMContext, ctx: AppContext) -> None:
        renderer = _RENDERERS.get(callback_data.to)
        if renderer is None:
            await cb.answer(texts.STALE_BUTTON, show_alert=True)
            return
        await cb.answer()
        await renderer(cb, state, ctx, spec)

    # ---- step 1: service ----
    @router.callback_query(ServiceCb.filter(), StateFilter(_state(spec, "service")))
    async def pick_service(cb: CallbackQuery, callback_data: ServiceCb, state: FSMContext, ctx: AppContext) -> None:
        service = await ctx.catalog.get_service(callback_data.id)
        if service is None or not service.is_active:
            await cb.answer(texts.service_unavailable(), show_alert=True)
            await show_services(cb, state, ctx, spec)
            return
        await cb.answer()
        await state.update_data(
            service_id=service.id,
            master_id=None,
            any_master=False,
            assigned_master_id=None,
            date=None,
            minute=None,
        )
        await show_masters(cb, state, ctx, spec)

    # ---- step 2: master ----
    @router.callback_query(MasterCb.filter(), StateFilter(_state(spec, "master")))
    async def pick_master(cb: CallbackQuery, callback_data: MasterCb, state: FSMContext, ctx: AppContext) -> None:
        data = await state.get_data()
        service_id = data.get("service_id")
        if service_id is None:
            await cb.answer(texts.STALE_BUTTON, show_alert=True)
            return
        if callback_data.id:
            masters = await ctx.catalog.masters_for_service(service_id)
            if callback_data.id not in {m.id for m in masters}:
                await cb.answer(texts.service_unavailable(), show_alert=True)
                await show_masters(cb, state, ctx, spec)
                return
        await cb.answer()
        await state.update_data(
            master_id=callback_data.id,
            any_master=callback_data.id == 0,
            assigned_master_id=None,
            date=None,
            minute=None,
        )
        await show_dates(cb, state, ctx, spec)

    # ---- step 3: date ----
    @router.callback_query(DateCb.filter(), StateFilter(_state(spec, "date")))
    async def pick_date(cb: CallbackQuery, callback_data: DateCb, state: FSMContext, ctx: AppContext) -> None:
        day = parse_iso_date(callback_data.value)
        if day is None:
            await cb.answer(texts.STALE_BUTTON, show_alert=True)
            return
        await cb.answer()
        await state.update_data(date=day.isoformat(), assigned_master_id=None, minute=None)
        await show_times(cb, state, ctx, spec)

    # ---- step 4: time ----
    @router.callback_query(TimeCb.filter(), StateFilter(_state(spec, "time")))
    async def pick_time(cb: CallbackQuery, callback_data: TimeCb, state: FSMContext, ctx: AppContext) -> None:
        data = await state.get_data()
        day = parse_iso_date(data.get("date"))
        if day is None or data.get("service_id") is None or data.get("master_id") is None:
            await cb.answer(texts.STALE_BUTTON, show_alert=True)
            return
        master = await ctx.booking.resolve_master(
            data["service_id"], data["master_id"], day, callback_data.minute, admin=spec.by_admin
        )
        if master is None:
            await cb.answer(texts.SLOT_TAKEN_ALERT, show_alert=True)
            await show_times(cb, state, ctx, spec, notice=texts.slot_taken_notice() + "\n\n")
            return
        await cb.answer()
        suggested = None
        if not spec.by_admin:
            user = await ctx.users.get(cb.from_user.id)
            suggested = (user.contact_name if user and user.contact_name else cb.from_user.full_name)[:50]
        await state.update_data(
            minute=callback_data.minute, assigned_master_id=master.id, suggested_name=suggested
        )
        await show_name(cb, state, ctx, spec)

    # ---- step 5a: name ----
    @router.callback_query(StepCb.filter(F.action == "name_keep"), StateFilter(_state(spec, "name")))
    async def name_keep(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
        data = await state.get_data()
        name = data.get("suggested_name")
        if not name:
            await cb.answer(texts.STALE_BUTTON, show_alert=True)
            return
        await cb.answer()
        await state.update_data(client_name=name)
        await show_phone(cb, state, ctx, spec)

    @router.message(StateFilter(_state(spec, "name")), TEXT_INPUT)
    async def name_typed(message: Message, state: FSMContext, ctx: AppContext) -> None:
        name = validate_name(message.text or "")
        if name is None:
            await message.answer(texts.invalid_name())
            return
        await state.update_data(client_name=name)
        await show_phone(message, state, ctx, spec)

    # ---- step 5b: phone ----
    if not spec.by_admin:

        @router.message(StateFilter(_state(spec, "phone")), F.text == BTN_BACK)
        async def phone_back(message: Message, state: FSMContext, ctx: AppContext) -> None:
            await remove_reply_keyboard(message)
            await show_name(message, state, ctx, spec)

        @router.message(StateFilter(_state(spec, "phone")), F.text == BTN_HOME)
        async def phone_home(message: Message, state: FSMContext, ctx: AppContext) -> None:
            await remove_reply_keyboard(message)
            await show_main_menu(message, state, ctx)

    @router.message(StateFilter(_state(spec, "phone")), F.contact)
    async def phone_contact(message: Message, state: FSMContext, ctx: AppContext) -> None:
        phone = normalize_contact_phone(message.contact.phone_number) if message.contact else None
        if phone is None:
            await message.answer(texts.invalid_phone())
            return
        await state.update_data(client_phone=phone)
        await show_confirm(message, state, ctx, spec, remove_reply_kb=True)

    @router.message(StateFilter(_state(spec, "phone")), TEXT_INPUT)
    async def phone_typed(message: Message, state: FSMContext, ctx: AppContext) -> None:
        raw = (message.text or "").strip().removeprefix("📞").strip()
        if spec.by_admin and raw in {"-", "—", "–"}:
            phone: str | None = ""
        else:
            phone = normalize_phone(raw)
        if phone is None:
            await message.answer(texts.invalid_phone())
            return
        await state.update_data(client_phone=phone)
        await show_confirm(message, state, ctx, spec, remove_reply_kb=not spec.by_admin)

    @router.callback_query(StepCb.filter(F.action == "phone_skip"), StateFilter(_state(spec, "phone")))
    async def phone_skip(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
        await cb.answer()
        await state.update_data(client_phone="")
        await show_confirm(cb, state, ctx, spec)

    # ---- step 6: confirmation ----
    @router.callback_query(ConfirmCb.filter(F.action == "no"), StateFilter(_state(spec, "confirm")))
    async def confirm_no(cb: CallbackQuery, state: FSMContext) -> None:
        await cb.answer()
        await state.clear()
        await edit_or_send(cb, texts.booking_flow_cancelled(), markup(nav_row(spec.exit_cb, MENU_MAIN)))

    @router.callback_query(ConfirmCb.filter(F.action == "yes"), StateFilter(_state(spec, "confirm")))
    async def confirm_yes(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
        user_id = cb.from_user.id
        # The lock + state re-check make a double tap harmless: the second tap sees a cleared state.
        async with ctx.locks.get(user_id):
            if await state.get_state() != st_confirm.state:
                await cb.answer(texts.ALREADY_DONE, show_alert=True)
                return
            data = await state.get_data()
            day = parse_iso_date(data.get("date"))
            if day is None or data.get("minute") is None or not data.get("service_id"):
                await cb.answer(texts.STALE_BUTTON, show_alert=True)
                await state.clear()
                return
            try:
                appt = await ctx.booking.create_appointment(
                    user_tg_id=None if spec.by_admin else user_id,
                    service_id=data["service_id"],
                    master_id=data.get("assigned_master_id") or 0,
                    any_master=bool(data.get("any_master")),
                    day=day,
                    start_min=data["minute"],
                    client_name=data.get("client_name", ""),
                    client_phone=data.get("client_phone", ""),
                    by_admin=spec.by_admin,
                )
            except SlotUnavailableError:
                # Double-booking guard: the slot was taken between selection and confirmation.
                await cb.answer(texts.SLOT_TAKEN_ALERT, show_alert=True)
                await show_times(cb, state, ctx, spec, notice=texts.slot_taken_notice() + "\n\n")
                return
            await state.clear()

        await cb.answer()
        if spec.by_admin:
            await edit_or_send(cb, texts.admin_booking_created(appt), admin_after_create_kb(appt))
            return

        try:
            await ctx.users.set_contact(user_id, appt.client_name, appt.client_phone)
        except Exception:
            logger.exception("Could not remember contact details of user %s", user_id)
        await edit_or_send(cb, texts.booking_success(appt), after_booking_kb())
        ctx.notifier.notify_admins_bg(
            texts.admin_new_booking(appt, cb.from_user.username, cb.from_user.id)
        )

    return router
