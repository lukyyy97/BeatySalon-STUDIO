"""Booking logic: availability, race-safe creation and cancellation of appointments."""
import datetime as dt
import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, replace
from zoneinfo import ZoneInfo

import aiosqlite

from bot.database.db import Database
from bot.database.models import Appointment, Master, Service, TimeOff, WorkDay
from bot.database.repositories import AppointmentRepo, CatalogRepo, ScheduleRepo, UserRepo
from bot.services.slots import compute_free_slots

logger = logging.getLogger(__name__)


class BookingError(Exception):
    """Base class for booking errors."""


class SlotUnavailableError(BookingError):
    """The requested slot is not free (anymore)."""


class AppointmentNotFoundError(BookingError):
    """No such appointment (or it belongs to somebody else)."""


class AppointmentStateError(BookingError):
    """Appointment cannot be changed; `reason` is 'cancelled' or 'started'."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class BookingConfig:
    tz: ZoneInfo
    horizon_days: int = 14
    slot_step_min: int = 30
    min_lead_minutes: int = 60


@dataclass(slots=True)
class _Calendar:
    """Everything needed to compute free slots of one master for a range of dates."""

    week: dict[int, WorkDay]
    off: dict[dt.date, list[TimeOff]]
    busy: dict[dt.date, list[tuple[int, int]]]


@dataclass(frozen=True, slots=True)
class _MasterOption:
    master: Master
    slots: list[int]
    busy_count: int


class BookingService:
    def __init__(
        self,
        db: Database,
        config: BookingConfig,
        catalog: CatalogRepo,
        schedule: ScheduleRepo,
        appointments: AppointmentRepo,
        users: UserRepo,
        now_func: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self._db = db
        self._config = config
        self._catalog = catalog
        self._schedule = schedule
        self._appointments = appointments
        self._users = users
        self._now_func = now_func

    # ------------------------------------------------------------------ time
    def now(self) -> dt.datetime:
        """Current salon-local time as a naive datetime."""
        if self._now_func is not None:
            return self._now_func()
        return dt.datetime.now(self._config.tz).replace(tzinfo=None)

    def today(self) -> dt.date:
        return self.now().date()

    # ------------------------------------------------------------ availability
    async def available_dates(self, service_id: int, master_id: int, *, admin: bool = False) -> list[dt.date]:
        """Dates within the booking horizon that have at least one free slot.

        `master_id == 0` means "any master that performs the service".
        """
        now = self.now()
        first = now.date()
        horizon = self._config.horizon_days
        last = first + dt.timedelta(days=horizon - 1)
        found: set[dt.date] = set()
        async with self._db.connection() as conn:
            service = await self._catalog.get_service(service_id, conn=conn)
            if service is None or not service.is_active:
                return []
            for master in await self._masters(conn, service_id, master_id):
                calendar = await self._load_calendar(conn, master.id, first, last)
                for offset in range(horizon):
                    day = first + dt.timedelta(days=offset)
                    if day not in found and self._day_slots(
                        calendar, day, service.duration_min, now, ignore_lead=admin
                    ):
                        found.add(day)
        return sorted(found)

    async def free_slots(
        self, service_id: int, master_id: int, day: dt.date, *, admin: bool = False
    ) -> list[int]:
        """Start minutes of free slots on a date (union over masters for 'any master')."""
        now = self.now()
        async with self._db.connection() as conn:
            service = await self._catalog.get_service(service_id, conn=conn)
            if service is None or not service.is_active:
                return []
            options = await self._master_options(conn, service, master_id, day, now, admin=admin)
        return sorted({slot for option in options for slot in option.slots})

    async def resolve_master(
        self, service_id: int, master_id: int, day: dt.date, start_min: int, *, admin: bool = False
    ) -> Master | None:
        """Pick the concrete master for a slot (least busy one when 'any master' was chosen)."""
        now = self.now()
        async with self._db.connection() as conn:
            service = await self._catalog.get_service(service_id, conn=conn)
            if service is None or not service.is_active:
                return None
            options = await self._master_options(conn, service, master_id, day, now, admin=admin)
        candidates = [option for option in options if start_min in option.slots]
        if not candidates:
            return None
        return min(candidates, key=lambda o: (o.busy_count, o.master.id)).master

    # ---------------------------------------------------------------- create
    async def create_appointment(
        self,
        *,
        user_tg_id: int | None,
        service_id: int,
        master_id: int,
        any_master: bool,
        day: dt.date,
        start_min: int,
        client_name: str,
        client_phone: str,
        by_admin: bool = False,
    ) -> Appointment:
        """Create an appointment atomically.

        The availability check and the INSERT happen inside one `BEGIN IMMEDIATE` transaction,
        so two clients can never grab the same slot. `master_id` is the preferred master; with
        `any_master=True` another free master is used if the preferred one got busy meanwhile.
        """
        now = self.now()
        try:
            async with self._db.transaction() as conn:
                service = await self._catalog.get_service(service_id, conn=conn)
                if service is None or not service.is_active:
                    raise SlotUnavailableError("service is not available")
                if not by_admin and day > now.date() + dt.timedelta(days=self._config.horizon_days - 1):
                    raise SlotUnavailableError("date is outside of the booking horizon")

                options = await self._master_options(
                    conn, service, 0 if any_master else master_id, day, now, admin=by_admin
                )
                free = [option for option in options if start_min in option.slots]
                if not free:
                    raise SlotUnavailableError("slot is taken")
                free.sort(key=lambda o: (o.master.id != master_id, o.busy_count, o.master.id))
                master = free[0].master

                if user_tg_id is not None:
                    await self._users.ensure(user_tg_id, conn=conn)

                end_min = start_min + service.duration_min
                starts_in = dt.datetime.combine(day, dt.time()) + dt.timedelta(minutes=start_min) - now
                appointment_id = await self._appointments.insert(
                    conn,
                    user_tg_id=user_tg_id,
                    service_id=service.id,
                    master_id=master.id,
                    day=day,
                    start_min=start_min,
                    end_min=end_min,
                    client_name=client_name,
                    client_phone=client_phone,
                    price=service.price,
                    duration_min=service.duration_min,
                    created_by="admin" if by_admin else "client",
                    # do not send a "24h before" reminder for a visit that is sooner than 24h away
                    reminder_24h_sent=starts_in <= dt.timedelta(hours=24),
                    reminder_2h_sent=starts_in <= dt.timedelta(hours=2),
                )
                appointment = await self._appointments.get(appointment_id, conn=conn)
        except sqlite3.IntegrityError as exc:  # unique index fired: somebody was faster
            raise SlotUnavailableError("slot is taken") from exc

        if appointment is None:  # pragma: no cover - defensive
            raise BookingError("appointment disappeared right after creation")
        logger.info(
            "Appointment #%s created: %s %s %s master=%s by_admin=%s",
            appointment.id, appointment.service_name, appointment.date, appointment.start_min,
            appointment.master_name, by_admin,
        )
        return appointment

    # ---------------------------------------------------------------- cancel
    async def cancel_appointment(
        self,
        appointment_id: int,
        *,
        cancelled_by: str,
        user_tg_id: int | None = None,
        allow_started: bool = False,
    ) -> Appointment:
        """Cancel an active appointment.

        When `user_tg_id` is given the appointment must belong to that user. Clients cannot
        cancel visits that have already started (`allow_started=False`).
        """
        async with self._db.transaction() as conn:
            appointment = await self._appointments.get(appointment_id, conn=conn)
            if appointment is None or (user_tg_id is not None and appointment.user_tg_id != user_tg_id):
                raise AppointmentNotFoundError(str(appointment_id))
            if not appointment.is_active:
                raise AppointmentStateError("cancelled")
            if not allow_started and appointment.starts_at() <= self.now():
                raise AppointmentStateError("started")
            await self._appointments.cancel(appointment_id, cancelled_by, conn=conn)
        logger.info("Appointment #%s cancelled by %s", appointment_id, cancelled_by)
        return replace(appointment, status="cancelled")

    # --------------------------------------------------------------- helpers
    async def _masters(self, conn: aiosqlite.Connection, service_id: int, master_id: int) -> list[Master]:
        masters = await self._catalog.masters_for_service(service_id, conn=conn)
        return [m for m in masters if m.id == master_id] if master_id else masters

    async def _load_calendar(
        self, conn: aiosqlite.Connection, master_id: int, first: dt.date, last: dt.date
    ) -> _Calendar:
        week = await self._schedule.get_week(master_id, conn=conn)
        off: dict[dt.date, list[TimeOff]] = {}
        for item in await self._schedule.time_off_in_range(master_id, first, last, conn=conn):
            off.setdefault(item.date, []).append(item)
        busy = await self._appointments.busy_in_range(master_id, first, last, conn=conn)
        return _Calendar(week=week, off=off, busy=busy)

    def _day_slots(
        self, calendar: _Calendar, day: dt.date, duration: int, now: dt.datetime, *, ignore_lead: bool
    ) -> list[int]:
        if day < now.date():
            return []
        work = calendar.week.get(day.weekday())
        if work is None:
            return []
        blocked = list(calendar.busy.get(day, ()))
        for item in calendar.off.get(day, ()):
            if item.start_min is None or item.end_min is None:
                return []  # the whole day is closed
            blocked.append((item.start_min, item.end_min))
        earliest = 0
        if day == now.date():
            earliest = now.hour * 60 + now.minute
            if not ignore_lead:
                earliest += self._config.min_lead_minutes
        return compute_free_slots(work, blocked, duration, self._config.slot_step_min, earliest)

    async def _master_options(
        self,
        conn: aiosqlite.Connection,
        service: Service,
        master_id: int,
        day: dt.date,
        now: dt.datetime,
        *,
        admin: bool,
    ) -> list[_MasterOption]:
        options: list[_MasterOption] = []
        for master in await self._masters(conn, service.id, master_id):
            calendar = await self._load_calendar(conn, master.id, day, day)
            slots = self._day_slots(calendar, day, service.duration_min, now, ignore_lead=admin)
            options.append(_MasterOption(master, slots, len(calendar.busy.get(day, ()))))
        return options
