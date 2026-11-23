"""Pure slot arithmetic (no I/O), easy to unit-test."""
from collections.abc import Iterable

from bot.database.models import WorkDay


def compute_free_slots(
    work: WorkDay,
    blocked: Iterable[tuple[int, int]],
    duration: int,
    step: int,
    earliest: int = 0,
) -> list[int]:
    """Return start minutes of every free slot of `duration` minutes inside the work day.

    * slots are laid out on a grid of `step` minutes starting at the beginning of the work day;
    * a slot must end before the work day ends and must not intersect the break or any
      `blocked` interval (existing appointments, closed time ranges);
    * slots starting before `earliest` are dropped (used for "today" and the minimum lead time).
    """
    intervals = list(blocked)
    if work.break_start is not None and work.break_end is not None:
        intervals.append((work.break_start, work.break_end))

    slots: list[int] = []
    start = work.start
    while start + duration <= work.end:
        end = start + duration
        if start >= earliest and all(end <= b_start or start >= b_end for b_start, b_end in intervals):
            slots.append(start)
        start += step
    return slots
