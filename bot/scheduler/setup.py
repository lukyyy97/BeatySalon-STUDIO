"""APScheduler wiring."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from bot.context import AppContext
from bot.scheduler.reminders import ReminderJob


def create_scheduler(ctx: AppContext) -> AsyncIOScheduler:
    """One interval job: every minute check the DB for reminders that are due."""
    scheduler = AsyncIOScheduler(timezone="UTC")
    job = ReminderJob(ctx.appointments, ctx.booking, ctx.notifier)
    scheduler.add_job(
        job.run,
        IntervalTrigger(minutes=1),
        id="appointment_reminders",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
        replace_existing=True,
    )
    return scheduler
