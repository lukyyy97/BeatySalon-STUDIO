"""Shared test fixtures: a seeded temporary database and a controllable clock."""
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from bot.database.db import Database
from bot.database.repositories import AppointmentRepo, CatalogRepo, ScheduleRepo, UserRepo
from bot.database.seed import seed_if_empty
from bot.services.booking import BookingConfig, BookingService

# Monday, 10:07 — masters of the seed data work on weekdays.
NOW = dt.datetime(2026, 11, 23, 10, 7)
MON = dt.date(2026, 11, 23)
TUE = dt.date(2026, 11, 24)
WED = dt.date(2026, 11, 25)
SUN = dt.date(2026, 11, 29)

# ids produced by the seed data
SVC_COLOR, SVC_CUT, SVC_MANI = 1, 2, 3
M_OLENA, M_IRYNA, M_MARIA, M_ANNA = 1, 2, 3, 4


class Clock:
    def __init__(self, value: dt.datetime) -> None:
        self.value = value

    def __call__(self) -> dt.datetime:
        return self.value


@dataclass
class Env:
    db: Database
    clock: Clock
    booking: BookingService
    users: UserRepo
    catalog: CatalogRepo
    schedule: ScheduleRepo
    appointments: AppointmentRepo


async def make_env(tmp_path: Path, now: dt.datetime = NOW) -> Env:
    db = Database(tmp_path / "test.db")
    await db.init()
    await seed_if_empty(db)
    users, catalog = UserRepo(db), CatalogRepo(db)
    schedule, appointments = ScheduleRepo(db), AppointmentRepo(db)
    clock = Clock(now)
    booking = BookingService(
        db,
        BookingConfig(tz=ZoneInfo("Europe/Kyiv"), horizon_days=14, slot_step_min=30, min_lead_minutes=60),
        catalog,
        schedule,
        appointments,
        users,
        now_func=clock,
    )
    return Env(db, clock, booking, users, catalog, schedule, appointments)
