"""All user-facing texts (Ukrainian) and message builders. Parse mode: HTML."""
import datetime as dt
import html
from collections.abc import Sequence

from bot.database.models import Appointment, Master, Service, TimeOff, WorkDay
from bot.utils.dates import (
    WEEKDAYS_FULL,
    WEEKDAYS_SHORT,
    format_date_long,
    format_date_short,
    format_duration,
    format_time_range,
)

STEPS_TOTAL = 6

ACCESS_DENIED = "⛔ У вас немає доступу до цієї команди."
ANY_MASTER = "Будь-який вільний майстер"
STALE_BUTTON = "Ця кнопка вже неактуальна. Натисніть /start, щоб відкрити меню."
ALREADY_DONE = "Цю дію вже виконано."
SLOT_TAKEN_ALERT = "😔 Цей час щойно зайняли. Оберіть інший."
GENERIC_ERROR = "⚠️ Щось пішло не так. Спробуйте ще раз або натисніть /start."
NOT_UNDERSTOOD = "Я не зрозумів повідомлення. Скористайтеся кнопками нижче або натисніть /start 👇"


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


# ------------------------------------------------------------------ client: menu
def welcome(salon_name: str, first_name: str) -> str:
    return (
        f"👋 Вітаємо, <b>{esc(first_name)}</b>!\n\n"
        f"Це бот салону краси <b>{esc(salon_name)}</b>. Тут ви можете:\n"
        "• записатися на послугу онлайн;\n"
        "• переглянути чи скасувати свої записи;\n"
        "• дізнатися ціни та знайти нас на мапі.\n\n"
        "Оберіть дію 👇"
    )


def services_info(services: Sequence[Service]) -> str:
    if not services:
        return "💇‍♀️ <b>Послуги та ціни</b>\n\nСписок послуг поки що порожній."
    lines = [
        f"• <b>{esc(s.name)}</b> — {s.price} грн, {format_duration(s.duration_min)}" for s in services
    ]
    return "💇‍♀️ <b>Послуги та ціни</b>\n\n" + "\n".join(lines) + "\n\nНатисніть «Записатися», щоб обрати зручний час."


def contacts(name: str, address: str, phone: str, hours: str) -> str:
    return (
        f"📍 <b>{esc(name)}</b>\n\n"
        f"🏠 Адреса: {esc(address)}\n"
        f"📞 Телефон: {esc(phone)}\n"
        f"🕒 Графік роботи: {esc(hours)}"
    )


# --------------------------------------------------------- booking flow (shared)
def _step(number: int, title: str) -> str:
    return f"<b>Крок {number} з {STEPS_TOTAL} · {title}</b>"


def step_service() -> str:
    return f"💇‍♀️ {_step(1, 'Послуга')}\n\nОберіть послугу, на яку бажаєте записатися:"


def no_services() -> str:
    return "😔 Наразі немає доступних послуг. Спробуйте, будь ласка, пізніше."


def service_unavailable() -> str:
    return "⚠️ Ця послуга більше недоступна. Оберіть іншу."


def step_master(service: Service) -> str:
    return (
        f"👩‍🎨 {_step(2, 'Майстер')}\n\n"
        f"Послуга: <b>{esc(service.name)}</b>\n\n"
        "Оберіть майстра або довіртеся нам — ми підберемо будь-кого вільного:"
    )


def no_masters(service_name: str) -> str:
    return (
        f"😔 Для послуги «{esc(service_name)}» поки немає доступних майстрів.\n"
        "Поверніться назад та оберіть іншу послугу."
    )


def step_date(service: Service, master_label: str) -> str:
    return (
        f"📆 {_step(3, 'Дата')}\n\n"
        f"Послуга: <b>{esc(service.name)}</b>\n"
        f"Майстер: <b>{esc(master_label)}</b>\n\n"
        "Оберіть зручний день (показано лише дні з вільним часом):"
    )


def no_dates(days: int) -> str:
    return (
        f"😔 На найближчі {days} днів вільного часу немає.\n"
        "Спробуйте обрати іншого майстра або зазирніть пізніше."
    )


def step_time(service: Service, master_label: str, day: dt.date) -> str:
    return (
        f"🕒 {_step(4, 'Час')}\n\n"
        f"Послуга: <b>{esc(service.name)}</b>\n"
        f"Майстер: <b>{esc(master_label)}</b>\n"
        f"Дата: <b>{format_date_long(day)}</b>\n\n"
        "Оберіть час початку:"
    )


def no_slots_for_date() -> str:
    return "😔 На цю дату вільного часу не залишилось. Оберіть, будь ласка, інший день."


def slot_taken_notice() -> str:
    return "😔 На жаль, цей час щойно зайняли. Оберіть, будь ласка, інший."


def step_name(suggested: str | None, by_admin: bool) -> str:
    head = f"👤 {_step(5, 'Контактні дані')}\n\n"
    if by_admin:
        return head + "Введіть ім’я клієнта повідомленням:"
    if suggested:
        return (
            head
            + f"Ми підставили ім’я з вашого профілю — <b>{esc(suggested)}</b>.\n"
            "Натисніть кнопку нижче, щоб залишити його, або просто напишіть інше ім’я."
        )
    return head + "Як до вас звертатися? Напишіть ваше ім’я повідомленням."


def name_saved(name: str) -> str:
    return f"👤 Ім’я: <b>{esc(name)}</b> ✅"


def step_phone(by_admin: bool) -> str:
    if by_admin:
        return (
            "📞 Введіть номер телефону клієнта у форматі <code>+380XXXXXXXXX</code> "
            "або натисніть «Без телефону»."
        )
    return (
        "📞 Вкажіть номер телефону для зв’язку.\n\n"
        "Натисніть «📱 Поділитися номером» або введіть його вручну "
        "у форматі <code>+380XXXXXXXXX</code>."
    )


def invalid_name() -> str:
    return (
        "⚠️ Ім’я має містити від 2 до 50 символів: літери, пробіл, дефіс або апостроф. "
        "Спробуйте ще раз."
    )


def invalid_phone() -> str:
    return (
        "⚠️ Не вдалося розпізнати номер. Введіть його у форматі "
        "<code>+380XXXXXXXXX</code> або <code>0XXXXXXXXX</code>."
    )


def booking_summary(
    service: Service,
    master_name: str,
    any_master: bool,
    day: dt.date,
    start_min: int,
    client_name: str,
    client_phone: str,
) -> str:
    master_line = esc(master_name) + (" (підібрано автоматично)" if any_master else "")
    return (
        f"📝 {_step(6, 'Підтвердження')}\n\n"
        "Перевірте, будь ласка, дані запису:\n\n"
        f"💇‍♀️ Послуга: <b>{esc(service.name)}</b>\n"
        f"👩‍🎨 Майстер: <b>{master_line}</b>\n"
        f"📅 Дата: <b>{format_date_long(day)}</b>\n"
        f"🕒 Час: <b>{format_time_range(start_min, start_min + service.duration_min)}</b>\n"
        f"⏱ Тривалість: {format_duration(service.duration_min)}\n"
        f"💰 Вартість: <b>{service.price} грн</b>\n\n"
        f"👤 Ім’я: {esc(client_name)}\n"
        f"📞 Телефон: {esc(client_phone) or '—'}"
    )


def booking_success(appt: Appointment) -> str:
    return (
        f"✅ <b>Запис підтверджено!</b> (№{appt.id})\n\n"
        f"{appointment_card(appt)}\n\n"
        "Ми надішлемо нагадування за 24 години та за 2 години до візиту. Чекаємо на вас! 💖"
    )


def booking_flow_cancelled() -> str:
    return "❌ Запис не створено. Ви можете почати знову будь-коли."


def admin_new_booking(appt: Appointment, username: str | None, tg_id: int | None) -> str:
    contact = f"@{esc(username)}" if username else "без username"
    return (
        f"🆕 <b>Новий запис №{appt.id}</b>\n\n"
        f"{appointment_card(appt, admin=True)}\n"
        f"🔗 Telegram: {contact} (id <code>{tg_id}</code>)"
    )


def admin_booking_created(appt: Appointment) -> str:
    return f"✅ <b>Запис №{appt.id} створено</b>\n\n{appointment_card(appt, admin=True)}"


# ------------------------------------------------------------------ appointments
def appointment_card(appt: Appointment, *, admin: bool = False, with_status: bool = False) -> str:
    lines = [
        f"💇‍♀️ Послуга: <b>{esc(appt.service_name)}</b>",
        f"👩‍🎨 Майстер: <b>{esc(appt.master_name)}</b>",
        f"📅 Дата: <b>{format_date_long(appt.date)}</b>",
        f"🕒 Час: <b>{format_time_range(appt.start_min, appt.end_min)}</b>",
        f"⏱ Тривалість: {format_duration(appt.duration_min)}",
        f"💰 Вартість: <b>{appt.price} грн</b>",
    ]
    if admin:
        lines.append(f"👤 Клієнт: {esc(appt.client_name)}")
        lines.append(f"📞 Телефон: {esc(appt.client_phone) or '—'}")
    if with_status:
        lines.append("✅ Статус: активний" if appt.is_active else "🚫 Статус: скасовано")
    return "\n".join(lines)


def my_bookings_header() -> str:
    return "📋 <b>Ваші майбутні записи</b>\n\nОберіть запис, щоб переглянути деталі або скасувати його:"


def no_bookings() -> str:
    return "📋 У вас поки немає активних записів.\n\nБажаєте записатися?"


def cancel_ask(appt: Appointment) -> str:
    return f"❓ <b>Скасувати цей запис?</b>\n\n{appointment_card(appt)}"


def cancel_done() -> str:
    return "✅ Запис скасовано. Будемо раді бачити вас іншим разом!"


def cancel_started() -> str:
    return "⚠️ Цей візит уже розпочався або минув, тому скасувати запис неможливо."


def cancel_not_found() -> str:
    return "⚠️ Запис не знайдено або його вже скасовано."


def admin_client_cancelled(appt: Appointment) -> str:
    return (
        f"❌ <b>Клієнт скасував запис №{appt.id}</b>\n\n"
        f"{appointment_card(appt, admin=True)}\n\n"
        f"🔓 Звільнилося вікно: <b>{esc(appt.master_name)}</b>, "
        f"{format_date_short(appt.date)}, {format_time_range(appt.start_min, appt.end_min)}"
    )


def client_cancelled_by_admin(appt: Appointment) -> str:
    return (
        "😔 <b>Ваш запис скасовано адміністратором салону.</b>\n\n"
        f"{appointment_card(appt)}\n\n"
        "Перепрошуємо за незручності. Ви можете обрати інший час у меню «Записатися на послугу»."
    )


def reminder(appt: Appointment, kind: str, today: dt.date) -> str:
    if kind == "2h":
        head = "⏰ <b>Нагадування:</b> орієнтовно через 2 години ваш візит до нашого салону!"
    else:
        when = "сьогодні" if appt.date == today else "завтра"
        head = f"🔔 <b>Нагадування:</b> {when} на вас чекає запис у нашому салоні."
    return (
        f"{head}\n\n{appointment_card(appt)}\n\n"
        "Якщо плани змінилися, будь ласка, скасуйте запис — так ми зможемо запропонувати цей час іншому клієнту."
    )


# ------------------------------------------------------------------------- admin
def admin_menu(users: int, upcoming: int) -> str:
    return (
        "🛠 <b>Адмін-панель</b>\n\n"
        f"👥 Користувачів бота: <b>{users}</b>\n"
        f"📅 Майбутніх активних записів: <b>{upcoming}</b>\n\n"
        "Оберіть розділ:"
    )


def admin_schedule(day: dt.date, appts: Sequence[Appointment], master_name: str | None) -> str:
    header = f"📅 <b>Розклад: {format_date_long(day)}</b>\n"
    header += f"👩‍🎨 Майстер: <b>{esc(master_name)}</b>" if master_name else "👩‍🎨 Усі майстри"
    if not appts:
        return header + "\n\nЗаписів на цей день немає."
    blocks = [
        f"🕒 <b>{format_time_range(a.start_min, a.end_min)}</b> · {esc(a.service_name)}\n"
        f"      👩‍🎨 {esc(a.master_name)} · 👤 {esc(a.client_name)} · 📞 {esc(a.client_phone) or '—'}"
        for a in appts[:30]
    ]
    text = header + f"\nЗаписів: <b>{len(appts)}</b>\n\n" + "\n\n".join(blocks)
    if len(appts) > 30:
        text += "\n\n…показано перші 30 записів."
    return text


def admin_appt_card(appt: Appointment) -> str:
    return f"📌 <b>Запис №{appt.id}</b>\n\n{appointment_card(appt, admin=True, with_status=True)}"


def admin_cancel_ask(appt: Appointment) -> str:
    return f"❓ <b>Скасувати запис №{appt.id}?</b>\n\n{appointment_card(appt, admin=True)}"


def admin_cancel_done(appt: Appointment, client_notified: bool) -> str:
    note = (
        "Клієнта сповіщено." if client_notified else "Клієнт не користується ботом — зв’яжіться з ним самостійно."
    )
    return f"✅ Запис №{appt.id} скасовано. {note}"


def admin_services_list(services: Sequence[Service]) -> str:
    if not services:
        return "💇‍♀️ <b>Послуги</b>\n\nПослуг поки немає. Додайте першу."
    lines = [
        f"{'✅' if s.is_active else '🙈'} <b>{esc(s.name)}</b> — {s.price} грн, {format_duration(s.duration_min)}"
        for s in services
    ]
    return "💇‍♀️ <b>Послуги</b>\n\n" + "\n".join(lines) + "\n\n🙈 — послуга прихована від клієнтів."


def service_card(service: Service, masters: Sequence[Master]) -> str:
    names = ", ".join(esc(m.name) for m in masters) or "ніхто не призначений"
    return (
        f"💇‍♀️ <b>{esc(service.name)}</b>\n\n"
        f"💰 Ціна: <b>{service.price} грн</b>\n"
        f"⏱ Тривалість: <b>{format_duration(service.duration_min)}</b>\n"
        f"👁 Статус: {'активна' if service.is_active else 'прихована від клієнтів'}\n"
        f"👩‍🎨 Майстри: {names}"
    )


def admin_masters_list(masters: Sequence[Master]) -> str:
    if not masters:
        return "👩‍🎨 <b>Майстри</b>\n\nМайстрів поки немає. Додайте першого."
    lines = [f"{'✅' if m.is_active else '🙈'} {esc(m.name)}" for m in masters]
    return "👩‍🎨 <b>Майстри</b>\n\n" + "\n".join(lines) + "\n\n🙈 — майстер прихований від клієнтів."


def week_lines(week: dict[int, WorkDay]) -> str:
    return "\n".join(
        f"{WEEKDAYS_SHORT[wd]}: {week[wd].describe() if wd in week else 'вихідний'}" for wd in range(7)
    )


def master_card(master: Master, services: Sequence[Service], week: dict[int, WorkDay]) -> str:
    names = ", ".join(esc(s.name) for s in services) or "не призначено"
    return (
        f"👩‍🎨 <b>{esc(master.name)}</b>\n\n"
        f"👁 Статус: {'активний' if master.is_active else 'прихований від клієнтів'}\n"
        f"💇‍♀️ Послуги: {names}\n\n"
        f"🗓 <b>Графік:</b>\n{week_lines(week)}"
    )


def weekday_name(weekday: int) -> str:
    return WEEKDAYS_FULL[weekday]


def time_off_label(item: TimeOff) -> str:
    if item.start_min is None or item.end_min is None:
        return "весь день"
    return format_time_range(item.start_min, item.end_min)


def timeoff_list(master: Master, items: Sequence[TimeOff]) -> str:
    head = f"🚫 <b>Вихідні та закриті слоти</b>\n👩‍🎨 Майстер: <b>{esc(master.name)}</b>\n\n"
    if not items:
        return head + "Майбутніх закриттів немає."
    lines = [f"• {format_date_short(i.date)} — {time_off_label(i)}" for i in items[:40]]
    return head + "\n".join(lines) + "\n\nНатисніть на запис нижче, щоб його видалити."


def broadcast_confirm(recipients: int) -> str:
    return (
        "👆 Так виглядатиме повідомлення.\n\n"
        f"👥 Отримувачів: <b>{recipients}</b>\n"
        "Розіслати його всім?"
    )


def broadcast_report(total: int, sent: int, blocked: int, failed: int) -> str:
    return (
        "📊 <b>Розсилку завершено</b>\n\n"
        f"👥 Усього отримувачів: <b>{total}</b>\n"
        f"✅ Доставлено: <b>{sent}</b>\n"
        f"🚫 Заблокували бота: <b>{blocked}</b>\n"
        f"⚠️ Помилки доставки: <b>{failed}</b>"
    )
