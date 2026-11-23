import asyncio
import datetime as dt

from bot.scheduler.reminders import ReminderJob
from bot.services.notifications import SendStatus
from tests.helpers import M_OLENA, SVC_CUT, WED, make_env


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.status = SendStatus.OK

    async def send(self, chat_id, text, *, reply_markup=None, mark_blocked=True):
        if self.status is SendStatus.OK:
            self.sent.append((chat_id, text))
        return self.status


async def _create(env, *, day, minute, user=111):
    return await env.booking.create_appointment(
        user_tg_id=user, service_id=SVC_CUT, master_id=M_OLENA, any_master=False,
        day=day, start_min=minute, client_name="Тест", client_phone="+380501234567",
    )


def _at(day, hour, minute=0):
    return dt.datetime.combine(day, dt.time(hour, minute))


def test_both_reminders_are_sent_exactly_once(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        appt = await _create(env, day=WED, minute=600)  # Wednesday 10:00
        notifier = FakeNotifier()
        job = ReminderJob(env.appointments, env.booking, notifier)

        env.clock.value = _at(dt.date(2026, 11, 24), 9)  # 25 h before: too early
        await job.run()
        assert notifier.sent == []

        env.clock.value = _at(dt.date(2026, 11, 24), 10, 30)  # 23.5 h before
        await job.run()
        await job.run()  # a second tick must not duplicate the reminder
        assert len(notifier.sent) == 1 and "завтра" in notifier.sent[0][1]

        env.clock.value = _at(WED, 7)  # 3 h before: nothing new
        await job.run()
        assert len(notifier.sent) == 1

        env.clock.value = _at(WED, 8, 30)  # 1.5 h before
        await job.run()
        await job.run()
        assert len(notifier.sent) == 2 and "2 години" in notifier.sent[1][1]

        stored = await env.appointments.get(appt.id)
        assert stored is not None and stored.reminder_24h_sent and stored.reminder_2h_sent

    asyncio.run(scenario())


def test_restart_inside_the_2h_window_sends_only_the_2h_reminder(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        await _create(env, day=WED, minute=600)
        notifier = FakeNotifier()
        job = ReminderJob(env.appointments, env.booking, notifier)
        env.clock.value = _at(WED, 8, 45)  # the bot was offline until now
        await job.run()
        assert len(notifier.sent) == 1 and "2 години" in notifier.sent[0][1]
        await job.run()
        assert len(notifier.sent) == 1

    asyncio.run(scenario())


def test_failed_delivery_is_retried_but_blocked_users_are_not(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        appt = await _create(env, day=WED, minute=600)
        notifier = FakeNotifier()
        job = ReminderJob(env.appointments, env.booking, notifier)
        env.clock.value = _at(WED, 8, 30)

        notifier.status = SendStatus.FAILED
        await job.run()
        stored = await env.appointments.get(appt.id)
        assert stored is not None and not stored.reminder_2h_sent  # will be retried

        notifier.status = SendStatus.OK
        await job.run()
        assert len(notifier.sent) == 1

        other = await _create(env, day=WED, minute=720, user=222)  # 12:00, created at 08:30
        env.clock.value = _at(WED, 10, 30)  # 1.5 h before the visit
        notifier.status = SendStatus.BLOCKED
        await job.run()
        stored = await env.appointments.get(other.id)
        assert stored is not None and stored.reminder_2h_sent  # undeliverable: do not retry forever

    asyncio.run(scenario())


def test_admin_created_and_cancelled_appointments_get_no_reminders(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        await _create(env, day=WED, minute=600, user=None)  # created by the admin, no Telegram user
        cancelled = await _create(env, day=WED, minute=720, user=333)
        await env.booking.cancel_appointment(cancelled.id, cancelled_by="client", user_tg_id=333)
        notifier = FakeNotifier()
        env.clock.value = _at(WED, 8, 30)
        await ReminderJob(env.appointments, env.booking, notifier).run()
        assert notifier.sent == []

    asyncio.run(scenario())
