import asyncio
import datetime as dt

import pytest

from bot.services.booking import (
    AppointmentNotFoundError,
    AppointmentStateError,
    SlotUnavailableError,
)
from tests.helpers import (
    M_IRYNA,
    M_MARIA,
    M_OLENA,
    MON,
    SUN,
    SVC_COLOR,
    SVC_CUT,
    SVC_MANI,
    TUE,
    WED,
    make_env,
)


def _book(env, *, day=TUE, minute=600, service=SVC_CUT, master=M_OLENA, any_master=False, user=111, by_admin=False):
    return env.booking.create_appointment(
        user_tg_id=user,
        service_id=service,
        master_id=master,
        any_master=any_master,
        day=day,
        start_min=minute,
        client_name="Тест",
        client_phone="+380501234567",
        by_admin=by_admin,
    )


def test_seed_data_is_present(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        assert [s.name for s in await env.catalog.list_services()] == ["Фарбування волосся", "Стрижка", "Манікюр"]
        assert len(await env.catalog.list_masters()) == 4
        assert [m.id for m in await env.catalog.masters_for_service(SVC_CUT)] == [M_OLENA, M_IRYNA]
        week = await env.schedule.get_week(M_OLENA)
        assert sorted(week) == [0, 1, 2, 3, 4]

    asyncio.run(scenario())


def test_today_slots_honour_lead_time_and_break(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)  # Monday 10:07, lead time 60 min
        slots = await env.booking.free_slots(SVC_CUT, M_OLENA, MON)
        assert slots == [690, 720, 840, 870, 900, 930, 960, 990, 1020]

    asyncio.run(scenario())


def test_weekend_and_unknown_service(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        assert await env.booking.free_slots(SVC_CUT, M_OLENA, SUN) == []
        assert await env.booking.free_slots(999, M_OLENA, TUE) == []
        dates = await env.booking.available_dates(SVC_CUT, M_OLENA)
        assert SUN not in dates and MON in dates
        assert len(dates) <= 14

    asyncio.run(scenario())


def test_booked_slot_blocks_overlapping_slots_only(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        await _book(env, minute=600)  # 10:00-11:00
        slots = await env.booking.free_slots(SVC_CUT, M_OLENA, TUE)
        assert slots == [540, 660, 690, 720, 840, 870, 900, 930, 960, 990, 1020]

    asyncio.run(scenario())


def test_double_booking_is_rejected(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        await _book(env, minute=600)
        with pytest.raises(SlotUnavailableError):
            await _book(env, minute=600, user=222)
        with pytest.raises(SlotUnavailableError):
            await _book(env, minute=630, user=222)  # overlaps 10:00-11:00

    asyncio.run(scenario())


def test_parallel_requests_for_one_slot_create_exactly_one_booking(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        results = await asyncio.gather(
            *(_book(env, minute=600, user=1000 + i) for i in range(8)), return_exceptions=True
        )
        created = [r for r in results if not isinstance(r, Exception)]
        rejected = [r for r in results if isinstance(r, SlotUnavailableError)]
        assert len(created) == 1
        assert len(rejected) == 7
        assert len(await env.appointments.for_day(TUE, M_OLENA)) == 1

    asyncio.run(scenario())


def test_any_master_spreads_load_then_runs_out(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        first = await _book(env, minute=600, master=0, any_master=True, user=1)
        second = await _book(env, minute=600, master=0, any_master=True, user=2)
        assert {first.master_id, second.master_id} == {M_OLENA, M_IRYNA}
        with pytest.raises(SlotUnavailableError):
            await _book(env, minute=600, master=0, any_master=True, user=3)

    asyncio.run(scenario())


def test_any_master_falls_back_when_preferred_master_got_busy(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        await _book(env, minute=600, master=M_OLENA, user=1)
        appt = await _book(env, minute=600, master=M_OLENA, any_master=True, user=2)
        assert appt.master_id == M_IRYNA
        # a client who picked a concrete master gets no fallback
        with pytest.raises(SlotUnavailableError):
            await _book(env, minute=600, master=M_OLENA, any_master=False, user=3)

    asyncio.run(scenario())


def test_resolve_master_prefers_the_least_busy(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        await _book(env, minute=540, master=M_OLENA, user=1)  # Olena already has one visit that day
        master = await env.booking.resolve_master(SVC_CUT, 0, TUE, 660)
        assert master is not None and master.id == M_IRYNA

    asyncio.run(scenario())


def test_cancel_frees_the_slot_and_checks_ownership(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        appt = await _book(env, minute=600, user=111)
        with pytest.raises(AppointmentNotFoundError):
            await env.booking.cancel_appointment(appt.id, cancelled_by="client", user_tg_id=999)
        cancelled = await env.booking.cancel_appointment(appt.id, cancelled_by="client", user_tg_id=111)
        assert cancelled.status == "cancelled"
        assert 600 in await env.booking.free_slots(SVC_CUT, M_OLENA, TUE)
        with pytest.raises(AppointmentStateError) as exc:
            await env.booking.cancel_appointment(appt.id, cancelled_by="client", user_tg_id=111)
        assert exc.value.reason == "cancelled"
        await _book(env, minute=600, user=222)  # the slot can be booked again

    asyncio.run(scenario())


def test_started_visit_cannot_be_cancelled_by_client(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        appt = await _book(env, minute=600, user=111)
        env.clock.value = dt.datetime(2026, 11, 24, 10, 30)
        with pytest.raises(AppointmentStateError) as exc:
            await env.booking.cancel_appointment(appt.id, cancelled_by="client", user_tg_id=111)
        assert exc.value.reason == "started"
        await env.booking.cancel_appointment(appt.id, cancelled_by="admin", allow_started=True)

    asyncio.run(scenario())


def test_time_off_closes_day_or_range(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        await env.schedule.add_time_off(M_OLENA, TUE)  # whole day
        await env.schedule.add_time_off(M_OLENA, WED, 540, 780)  # 09:00-13:00
        assert await env.booking.free_slots(SVC_CUT, M_OLENA, TUE) == []
        assert TUE not in await env.booking.available_dates(SVC_CUT, M_OLENA)
        wed_slots = await env.booking.free_slots(SVC_CUT, M_OLENA, WED)
        assert wed_slots[0] == 840  # morning is closed, afternoon (after the break) is open
        with pytest.raises(SlotUnavailableError):
            await _book(env, day=TUE, minute=600)
        # "any master" still finds the other master on the closed day
        appt = await _book(env, day=TUE, minute=660, master=0, any_master=True)
        assert appt.master_id == M_IRYNA

    asyncio.run(scenario())


def test_booking_rules_for_clients_and_admins(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        far = MON + dt.timedelta(days=30)
        with pytest.raises(SlotUnavailableError):
            await _book(env, day=dt.date(2026, 12, 7), minute=600)  # a Monday beyond the horizon
        with pytest.raises(SlotUnavailableError):
            await _book(env, day=MON, minute=600)  # in the past / inside the lead time
        # admins may book inside the lead time (walk-in client) and beyond the horizon
        walk_in = await _book(env, day=MON, minute=690, by_admin=True, user=None)
        assert walk_in.created_by == "admin" and walk_in.user_tg_id is None
        assert far.weekday() < 5  # sanity for the next line
        await _book(env, day=far, minute=600, by_admin=True, user=None)

    asyncio.run(scenario())


def test_reminder_flags_depend_on_how_soon_the_visit_is(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)  # Monday 10:07
        soon = await _book(env, day=MON, minute=690, by_admin=True)  # in ~1h20
        tomorrow = await _book(env, day=TUE, minute=540, user=2)  # in ~23h
        later = await _book(env, day=WED, minute=540, user=3)  # in ~47h
        assert (soon.reminder_24h_sent, soon.reminder_2h_sent) == (True, True)
        assert (tomorrow.reminder_24h_sent, tomorrow.reminder_2h_sent) == (True, False)
        assert (later.reminder_24h_sent, later.reminder_2h_sent) == (False, False)

    asyncio.run(scenario())


def test_manicure_and_colour_have_their_own_masters(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        assert await env.booking.resolve_master(SVC_MANI, M_OLENA, TUE, 600) is None
        mani = await env.booking.resolve_master(SVC_MANI, 0, TUE, 600)
        assert mani is not None and mani.id == M_MARIA
        colour = await _book(env, service=SVC_COLOR, minute=540, master=M_OLENA)
        assert colour.duration_min == 150 and colour.end_min == 540 + 150

    asyncio.run(scenario())


def test_hidden_service_or_master_cannot_be_booked(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        await env.catalog.update_master(M_OLENA, is_active=False)
        assert [m.id for m in await env.catalog.masters_for_service(SVC_CUT)] == [M_IRYNA]
        with pytest.raises(SlotUnavailableError):
            await _book(env, minute=600, master=M_OLENA)
        await env.catalog.update_service(SVC_CUT, is_active=False)
        with pytest.raises(SlotUnavailableError):
            await _book(env, minute=600, master=M_IRYNA)

    asyncio.run(scenario())


def test_toggle_master_service_link(tmp_path):
    async def scenario():
        env = await make_env(tmp_path)
        assert await env.catalog.toggle_master_service(M_MARIA, SVC_CUT) is True
        assert M_MARIA in [m.id for m in await env.catalog.masters_for_service(SVC_CUT)]
        assert await env.catalog.toggle_master_service(M_MARIA, SVC_CUT) is False

    asyncio.run(scenario())


def test_parallel_requests_for_different_slots_all_succeed(tmp_path):
    """Concurrency must not produce spurious 'database is locked' errors."""

    async def scenario():
        env = await make_env(tmp_path)
        slots = [540, 600, 660, 720, 840, 900]  # six different, non-overlapping hours
        results = await asyncio.gather(
            *(_book(env, minute=minute, user=2000 + i) for i, minute in enumerate(slots)),
            return_exceptions=True,
        )
        assert not [r for r in results if isinstance(r, Exception)], results
        assert len(await env.appointments.for_day(TUE, M_OLENA)) == len(slots)

    asyncio.run(scenario())
