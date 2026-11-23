"""Keyboards of the step-by-step booking flow (shared by the client and the admin flow)."""
import datetime as dt
from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot.callbacks import ConfirmCb, DateCb, MasterCb, MenuCb, ServiceCb, StepCb, TimeCb
from bot.database.models import Master, Service
from bot.keyboards.common import BTN_BACK, BTN_HOME, MENU_MAIN, btn, chunk, markup
from bot.texts import ANY_MASTER
from bot.utils.dates import format_date_button, format_duration, format_minutes

BTN_SHARE_PHONE = "📱 Поділитися номером"


def services_kb(services: Sequence[Service], nav: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    rows = [
        [btn(f"{s.name} · {s.price} грн · {format_duration(s.duration_min)}", ServiceCb(id=s.id))]
        for s in services
    ]
    return markup(*rows, nav)


def masters_kb(masters: Sequence[Master], nav: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    rows = [[btn("🎲 " + ANY_MASTER, MasterCb(id=0))]]
    rows += [[btn(f"👩‍🎨 {m.name}", MasterCb(id=m.id))] for m in masters]
    return markup(*rows, nav)


def dates_kb(dates: Sequence[dt.date], nav: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    buttons = [btn(format_date_button(d), DateCb(value=d.isoformat())) for d in dates]
    return markup(*chunk(buttons, 3), nav)


def times_kb(minutes: Sequence[int], nav: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    buttons = [btn(format_minutes(m), TimeCb(minute=m)) for m in minutes]
    return markup(*chunk(buttons, 4), nav)


def name_kb(suggested: str | None, nav: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if suggested:
        rows.append([btn(f"✅ Залишити: {suggested}"[:60], StepCb(action="name_keep"))])
    return markup(*rows, nav)


def phone_skip_kb(nav: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return markup([btn("⏭ Без телефону", StepCb(action="phone_skip"))], nav)


def phone_request_kb(saved_phone: str | None) -> ReplyKeyboardMarkup:
    """Reply keyboard of the phone step: contact request, saved number, Back / Home."""
    rows = [[KeyboardButton(text=BTN_SHARE_PHONE, request_contact=True)]]
    if saved_phone:
        rows.append([KeyboardButton(text=f"📞 {saved_phone}")])
    rows.append([KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_HOME)])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="+380XXXXXXXXX",
    )


def confirm_kb(nav: list[InlineKeyboardButton], yes_text: str) -> InlineKeyboardMarkup:
    return markup(
        [btn(yes_text, ConfirmCb(action="yes")), btn("❌ Скасувати", ConfirmCb(action="no"))],
        nav,
    )


def after_booking_kb() -> InlineKeyboardMarkup:
    return markup([btn("📋 Мої записи", MenuCb(action="my"))], [btn("🏠 В головне меню", MENU_MAIN)])


__all__ = [
    "BTN_SHARE_PHONE",
    "after_booking_kb",
    "confirm_kb",
    "dates_kb",
    "masters_kb",
    "name_kb",
    "phone_request_kb",
    "phone_skip_kb",
    "services_kb",
    "times_kb",
]
