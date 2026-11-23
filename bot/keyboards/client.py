"""Client-side keyboards: main menu, my bookings, info screens."""
from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.callbacks import AdmMenuCb, MenuCb, MyApptCb
from bot.database.models import Appointment
from bot.keyboards.common import MENU_MAIN, btn, markup, nav_row
from bot.utils.dates import format_minutes


def main_menu_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [btn("📅 Записатися на послугу", MenuCb(action="book"))],
        [btn("📋 Мої записи", MenuCb(action="my"))],
        [btn("💇‍♀️ Послуги та ціни", MenuCb(action="services"))],
        [btn("📍 Контакти та адреса", MenuCb(action="contacts"))],
    ]
    if is_admin:
        rows.append([btn("🛠 Адмін-панель", AdmMenuCb(action="main"))])
    return markup(*rows)


def my_bookings_kb(appts: Sequence[Appointment]) -> InlineKeyboardMarkup:
    rows = [
        [
            btn(
                f"📅 {a.date:%d.%m} {format_minutes(a.start_min)} · {a.service_name}"[:60],
                MyApptCb(action="view", id=a.id),
            )
        ]
        for a in appts[:20]
    ]
    return markup(*rows, nav_row(MENU_MAIN))


def no_bookings_kb() -> InlineKeyboardMarkup:
    return markup([btn("📅 Записатися на послугу", MenuCb(action="book"))], nav_row(MENU_MAIN))


def appointment_kb(appt_id: int) -> InlineKeyboardMarkup:
    return markup(
        [btn("❌ Скасувати запис", MyApptCb(action="ask", id=appt_id))],
        nav_row(MenuCb(action="my")),
    )


def cancel_confirm_kb(appt_id: int) -> InlineKeyboardMarkup:
    return markup(
        [
            btn("✅ Так, скасувати", MyApptCb(action="yes", id=appt_id)),
            btn("↩️ Ні, залишити", MyApptCb(action="view", id=appt_id)),
        ],
        nav_row(MyApptCb(action="view", id=appt_id)),
    )


def cancel_done_kb() -> InlineKeyboardMarkup:
    return markup(nav_row(MenuCb(action="my")))


def services_info_kb() -> InlineKeyboardMarkup:
    return markup([btn("📅 Записатися на послугу", MenuCb(action="book"))], nav_row(MENU_MAIN))


def contacts_kb(map_url: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if map_url.startswith(("http://", "https://")):
        rows.append([InlineKeyboardButton(text="🗺 Відкрити на мапі", url=map_url)])
    return markup(*rows, nav_row(MENU_MAIN))


def reminder_kb(appt_id: int) -> InlineKeyboardMarkup:
    return markup(
        [btn("❌ Скасувати запис", MyApptCb(action="ask", id=appt_id))],
        [btn("📋 Мої записи", MenuCb(action="my"))],
    )
