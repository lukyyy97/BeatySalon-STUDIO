"""Application context: all long-lived services in one object injected into handlers."""
from dataclasses import dataclass

from aiogram import Bot

from bot.config import Settings
from bot.database.db import Database
from bot.database.repositories import AppointmentRepo, CatalogRepo, ScheduleRepo, UserRepo
from bot.services.booking import BookingConfig, BookingService
from bot.services.broadcast import BroadcastService
from bot.services.notifications import Notifier
from bot.utils.locks import KeyedLocks
from bot.utils.tasks import BackgroundTasks


@dataclass(slots=True)
class AppContext:
    settings: Settings
    admin_ids: frozenset[int]
    db: Database
    users: UserRepo
    catalog: CatalogRepo
    schedule: ScheduleRepo
    appointments: AppointmentRepo
    booking: BookingService
    notifier: Notifier
    broadcaster: BroadcastService
    locks: KeyedLocks
    tasks: BackgroundTasks

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


def build_context(settings: Settings, db: Database, bot: Bot) -> AppContext:
    users = UserRepo(db)
    catalog = CatalogRepo(db)
    schedule = ScheduleRepo(db)
    appointments = AppointmentRepo(db)
    tasks = BackgroundTasks()
    admin_ids = settings.admin_ids

    booking = BookingService(
        db,
        BookingConfig(
            tz=settings.tz,
            horizon_days=settings.booking_horizon_days,
            slot_step_min=settings.slot_step_min,
            min_lead_minutes=settings.min_lead_minutes,
        ),
        catalog,
        schedule,
        appointments,
        users,
    )
    notifier = Notifier(bot, users, admin_ids, tasks)
    return AppContext(
        settings=settings,
        admin_ids=admin_ids,
        db=db,
        users=users,
        catalog=catalog,
        schedule=schedule,
        appointments=appointments,
        booking=booking,
        notifier=notifier,
        broadcaster=BroadcastService(notifier, users),
        locks=KeyedLocks(),
        tasks=tasks,
    )
