"""Admin panel keyboards."""
import datetime as dt
from collections.abc import Sequence

from aiogram.types import InlineKeyboardMarkup

from bot import texts
from bot.callbacks import AdmApptCb, AdmCatCb, AdmMenuCb, AdmOffCb, AdmSchedCb, BroadcastCb
from bot.database.models import Appointment, Master, Service, TimeOff, WorkDay
from bot.keyboards.common import MENU_MAIN, btn, chunk, markup, nav_row
from bot.utils.dates import WEEKDAYS_SHORT, format_date_short, format_minutes

_MENU = AdmMenuCb(action="main")


def _mark(active: bool) -> str:
    return "✅" if active else "🙈"


def admin_menu_kb() -> InlineKeyboardMarkup:
    return markup(
        [btn("📅 Розклад", AdmMenuCb(action="schedule")), btn("➕ Додати запис", AdmMenuCb(action="add"))],
        [btn("💇 Послуги", AdmMenuCb(action="services")), btn("👩‍🎨 Майстри", AdmMenuCb(action="masters"))],
        [btn("🚫 Вихідні та слоти", AdmMenuCb(action="timeoff")), btn("📣 Розсилка", AdmMenuCb(action="broadcast"))],
        [btn("🏠 В головне меню", MENU_MAIN)],
    )


# --------------------------------------------------------------------- schedule
def schedule_kb(
    appts: Sequence[Appointment],
    day: dt.date,
    master_id: int,
    masters: Sequence[Master],
    today: dt.date,
) -> InlineKeyboardMarkup:
    iso = day.isoformat()
    rows = [
        [
            btn(
                f"{format_minutes(a.start_min)} · {a.client_name} · {a.service_name}"[:60],
                AdmApptCb(action="view", id=a.id),
            )
        ]
        for a in appts[:30]
    ]
    filters = [btn(("● " if master_id == 0 else "") + "Усі майстри", AdmSchedCb(d=iso, m=0))]
    filters += [btn(("● " if master_id == m.id else "") + m.name, AdmSchedCb(d=iso, m=m.id)) for m in masters]
    day_nav = [
        btn("◀️", AdmSchedCb(d=(day - dt.timedelta(days=1)).isoformat(), m=master_id)),
        btn("Сьогодні", AdmSchedCb(d=today.isoformat(), m=master_id)),
        btn("▶️", AdmSchedCb(d=(day + dt.timedelta(days=1)).isoformat(), m=master_id)),
    ]
    return markup(
        *rows,
        *chunk(filters, 2),
        day_nav,
        [btn("📆 Інша дата", AdmMenuCb(action="sched_date")), btn("➕ Додати запис", AdmMenuCb(action="add"))],
        nav_row(_MENU),
    )


def admin_appt_kb(appt: Appointment) -> InlineKeyboardMarkup:
    rows = [[btn("❌ Скасувати запис", AdmApptCb(action="ask", id=appt.id))]] if appt.is_active else []
    return markup(*rows, nav_row(AdmSchedCb(d=appt.date.isoformat(), m=0)))


def admin_cancel_confirm_kb(appt_id: int) -> InlineKeyboardMarkup:
    return markup(
        [
            btn("✅ Так, скасувати", AdmApptCb(action="yes", id=appt_id)),
            btn("↩️ Ні, залишити", AdmApptCb(action="view", id=appt_id)),
        ],
        nav_row(AdmApptCb(action="view", id=appt_id)),
    )


def admin_after_cancel_kb(day: dt.date) -> InlineKeyboardMarkup:
    return markup(
        [btn("📅 Розклад на цей день", AdmSchedCb(d=day.isoformat(), m=0))],
        nav_row(_MENU),
    )


def admin_after_create_kb(appt: Appointment) -> InlineKeyboardMarkup:
    return markup(
        [btn("📅 Розклад на цей день", AdmSchedCb(d=appt.date.isoformat(), m=0))],
        [btn("➕ Додати ще один запис", AdmMenuCb(action="add"))],
        nav_row(_MENU),
    )


# --------------------------------------------------------------------- services
def admin_services_kb(services: Sequence[Service]) -> InlineKeyboardMarkup:
    rows = [
        [btn(f"{_mark(s.is_active)} {s.name} · {s.price} грн"[:60], AdmCatCb(action="svc", id=s.id))]
        for s in services
    ]
    rows.append([btn("➕ Додати послугу", AdmCatCb(action="svc_new"))])
    return markup(*rows, nav_row(_MENU))


def admin_service_kb(service: Service) -> InlineKeyboardMarkup:
    toggle = "🙈 Сховати" if service.is_active else "👁 Показати"
    return markup(
        [
            btn("✏️ Назва", AdmCatCb(action="svc_edit", id=service.id, extra=1)),
            btn("💰 Ціна", AdmCatCb(action="svc_edit", id=service.id, extra=2)),
            btn("⏱ Тривалість", AdmCatCb(action="svc_edit", id=service.id, extra=3)),
        ],
        [btn(toggle, AdmCatCb(action="svc_toggle", id=service.id))],
        nav_row(AdmMenuCb(action="services")),
    )


# ---------------------------------------------------------------------- masters
def admin_masters_kb(masters: Sequence[Master]) -> InlineKeyboardMarkup:
    rows = [[btn(f"{_mark(m.is_active)} {m.name}", AdmCatCb(action="mst", id=m.id))] for m in masters]
    rows.append([btn("➕ Додати майстра", AdmCatCb(action="mst_new"))])
    return markup(*rows, nav_row(_MENU))


def admin_master_kb(master: Master) -> InlineKeyboardMarkup:
    toggle = "🙈 Сховати" if master.is_active else "👁 Показати"
    return markup(
        [
            btn("✏️ Ім’я", AdmCatCb(action="mst_rename", id=master.id)),
            btn("💇 Послуги", AdmCatCb(action="mst_svcs", id=master.id)),
        ],
        [
            btn("🗓 Графік", AdmCatCb(action="mst_sched", id=master.id)),
            btn(toggle, AdmCatCb(action="mst_toggle", id=master.id)),
        ],
        nav_row(AdmMenuCb(action="masters")),
    )


def admin_master_services_kb(
    master_id: int, services: Sequence[Service], linked: set[int]
) -> InlineKeyboardMarkup:
    rows = [
        [
            btn(
                f"{'✅' if s.id in linked else '☐'} {s.name}"[:60],
                AdmCatCb(action="mst_svc_t", id=master_id, extra=s.id),
            )
        ]
        for s in services
    ]
    return markup(*rows, nav_row(AdmCatCb(action="mst", id=master_id)))


def admin_week_kb(master_id: int, week: dict[int, WorkDay]) -> InlineKeyboardMarkup:
    rows = [
        [
            btn(
                f"{WEEKDAYS_SHORT[wd]} · {week[wd].describe() if wd in week else 'вихідний'}"[:60],
                AdmCatCb(action="mst_day", id=master_id, extra=wd),
            )
        ]
        for wd in range(7)
    ]
    return markup(*rows, nav_row(AdmCatCb(action="mst", id=master_id)))


def admin_day_kb(master_id: int, weekday: int) -> InlineKeyboardMarkup:
    return markup(
        [btn("✏️ Задати години", AdmCatCb(action="mst_day_set", id=master_id, extra=weekday))],
        [btn("🚫 Зробити вихідним", AdmCatCb(action="mst_day_off", id=master_id, extra=weekday))],
        nav_row(AdmCatCb(action="mst_sched", id=master_id)),
    )


# --------------------------------------------------------------------- time off
def timeoff_masters_kb(masters: Sequence[Master]) -> InlineKeyboardMarkup:
    rows = [[btn(f"👩‍🎨 {m.name}", AdmOffCb(action="list", m=m.id))] for m in masters]
    return markup(*rows, nav_row(_MENU))


def timeoff_list_kb(master_id: int, items: Sequence[TimeOff]) -> InlineKeyboardMarkup:
    rows = [
        [
            btn(
                f"🗑 {format_date_short(i.date)} · {texts.time_off_label(i)}",
                AdmOffCb(action="del", m=master_id, id=i.id),
            )
        ]
        for i in items[:40]
    ]
    rows.append([btn("➕ Закрити день або слот", AdmOffCb(action="add", m=master_id))])
    return markup(*rows, nav_row(AdmMenuCb(action="timeoff")))


def timeoff_add_kb(master_id: int, today: dt.date) -> InlineKeyboardMarkup:
    tomorrow = today + dt.timedelta(days=1)
    return markup(
        [
            btn("Сьогодні", AdmOffCb(action="quick", m=master_id, v=today.isoformat())),
            btn("Завтра", AdmOffCb(action="quick", m=master_id, v=tomorrow.isoformat())),
        ],
        nav_row(AdmOffCb(action="list", m=master_id)),
    )


def timeoff_scope_kb(master_id: int) -> InlineKeyboardMarkup:
    return markup(
        [
            btn("🚫 Весь день", AdmOffCb(action="whole", m=master_id)),
            btn("🕒 Певні години", AdmOffCb(action="hours", m=master_id)),
        ],
        nav_row(AdmOffCb(action="add", m=master_id)),
    )


def timeoff_done_kb(master_id: int, first_day: dt.date) -> InlineKeyboardMarkup:
    return markup(
        [btn("📅 Розклад на цей день", AdmSchedCb(d=first_day.isoformat(), m=master_id))],
        nav_row(AdmOffCb(action="list", m=master_id)),
    )


# -------------------------------------------------------------------- broadcast
def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    return markup(
        [
            btn("✅ Розіслати", BroadcastCb(action="send")),
            btn("✏️ Змінити текст", BroadcastCb(action="edit")),
        ],
        [btn("❌ Скасувати", BroadcastCb(action="cancel"))],
        nav_row(_MENU),
    )
