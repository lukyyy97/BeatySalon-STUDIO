"""Appointment reminders (24h and 2h before the visit).

The job is stateless: every minute it asks the database which appointments still await
a reminder, so nothing is lost when the bot restarts. Sent reminders are flagged in the DB.
"""
import datetime as dt
import logging

from bot import texts
from bot.database.models import Appointment
from bot.database.repositories import AppointmentRepo
from bot.keyboards.client import reminder_kb
from bot.services.booking import BookingService
from bot.services.notifications import Notifier, SendStatus

logger = logging.getLogger(__name__)

_DAY = dt.timedelta(hours=24)
_TWO_HOURS = dt.timedelta(hours=2)


class ReminderJob:
    def __init__(self, appointments: AppointmentRepo, booking: BookingService, notifier: Notifier) -> None:
        self._appointments = appointments
        self._booking = booking
        self._notifier = notifier

    async def run(self) -> None:
        now = self._booking.now()
        try:
            due = await self._appointments.due_for_reminders(now.date(), now.date() + dt.timedelta(days=1))
        except Exception:
            logger.exception("Cannot load appointments for reminders")
            return
        for appointment in due:
            try:
                await self._process(appointment, now)
            except Exception:
                logger.exception("Reminder for appointment #%s failed", appointment.id)

    async def _process(self, appointment: Appointment, now: dt.datetime) -> None:
        remaining = appointment.starts_at() - now
        if remaining <= dt.timedelta(0):
            await self._mark_all(appointment)  # the visit has started: nothing to remind about
            return

        if not appointment.reminder_24h_sent and remaining <= _DAY:
            # If the bot was offline and we are already inside the 2h window, skip the 24h reminder.
            if remaining <= _TWO_HOURS or await self._send(appointment, "24h", now):
                await self._appointments.mark_reminder_sent(appointment.id, "24h")

        if not appointment.reminder_2h_sent and remaining <= _TWO_HOURS:
            if await self._send(appointment, "2h", now):
                await self._appointments.mark_reminder_sent(appointment.id, "2h")

    async def _mark_all(self, appointment: Appointment) -> None:
        if not appointment.reminder_24h_sent:
            await self._appointments.mark_reminder_sent(appointment.id, "24h")
        if not appointment.reminder_2h_sent:
            await self._appointments.mark_reminder_sent(appointment.id, "2h")

    async def _send(self, appointment: Appointment, kind: str, now: dt.datetime) -> bool:
        """Returns True when the reminder must be considered done (delivered or undeliverable)."""
        if appointment.user_tg_id is None:
            return True
        status = await self._notifier.send(
            appointment.user_tg_id,
            texts.reminder(appointment, kind, now.date()),
            reply_markup=reminder_kb(appointment.id),
        )
        if status is SendStatus.FAILED:
            logger.warning("Reminder %s for #%s will be retried", kind, appointment.id)
            return False
        return True
