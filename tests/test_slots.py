from bot.database.models import WorkDay
from bot.services.slots import compute_free_slots

DAY = WorkDay(start=9 * 60, end=18 * 60, break_start=13 * 60, break_end=14 * 60)


def _hm(slots):
    return [f"{s // 60:02d}:{s % 60:02d}" for s in slots]


def test_respects_break_and_work_end():
    slots = compute_free_slots(DAY, [], duration=60, step=30)
    assert "12:00" in _hm(slots)  # ends exactly when the break starts
    assert "12:30" not in _hm(slots)
    assert "13:00" not in _hm(slots)
    assert "14:00" in _hm(slots)
    assert _hm(slots)[-1] == "17:00"  # 17:30 would end after 18:00


def test_adjacent_appointments_do_not_conflict():
    slots = compute_free_slots(DAY, [(10 * 60, 11 * 60)], duration=60, step=30)
    hm = _hm(slots)
    assert "09:00" in hm  # 09:00-10:00 touches the busy interval but does not overlap
    assert "09:30" not in hm and "10:00" not in hm and "10:30" not in hm
    assert "11:00" in hm


def test_long_service_needs_a_long_gap():
    busy = [(10 * 60, 11 * 60)]
    slots = compute_free_slots(DAY, busy, duration=150, step=30)
    hm = _hm(slots)
    assert "09:00" not in hm  # 09:00-11:30 overlaps the busy block
    assert "11:00" not in hm  # 11:00-13:30 runs into the break
    assert "14:00" in hm


def test_earliest_drops_past_slots():
    slots = compute_free_slots(DAY, [], duration=60, step=30, earliest=15 * 60 + 1)
    assert _hm(slots)[0] == "15:30"


def test_service_longer_than_day_gives_nothing():
    assert compute_free_slots(WorkDay(9 * 60, 10 * 60), [], duration=90, step=30) == []
