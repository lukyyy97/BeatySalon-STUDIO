import datetime as dt

import aiosqlite

from bot.database.db import Database
from bot.database.models import TimeOff, WorkDay
from bot.utils.dates import format_minutes


def _fmt(value: int | None) -> str | None:
    return None if value is None else format_minutes(value)


class ScheduleRepo:
    """Weekly working hours and time-off (closed days / slots)."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_week(self, master_id: int, *, conn: aiosqlite.Connection | None = None) -> dict[int, WorkDay]:
        rows = await self._db.fetch_all(
            "SELECT * FROM work_schedule WHERE master_id = ?", (master_id,), conn=conn
        )
        return {row["weekday"]: WorkDay.from_row(row) for row in rows}

    async def set_day(
        self,
        master_id: int,
        weekday: int,
        start: int,
        end: int,
        break_start: int | None = None,
        break_end: int | None = None,
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO work_schedule (master_id, weekday, start_time, end_time, break_start, break_end)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(master_id, weekday) DO UPDATE SET
                start_time = excluded.start_time,
                end_time = excluded.end_time,
                break_start = excluded.break_start,
                break_end = excluded.break_end
            """,
            (master_id, weekday, _fmt(start), _fmt(end), _fmt(break_start), _fmt(break_end)),
            conn=conn,
        )

    async def clear_day(self, master_id: int, weekday: int) -> None:
        await self._db.execute(
            "DELETE FROM work_schedule WHERE master_id = ? AND weekday = ?", (master_id, weekday)
        )

    # ---- time off ----
    async def add_time_off(
        self,
        master_id: int,
        day: dt.date,
        start: int | None = None,
        end: int | None = None,
        reason: str | None = None,
    ) -> int:
        return await self._db.insert(
            "INSERT INTO time_off (master_id, date, start_time, end_time, reason) VALUES (?, ?, ?, ?, ?)",
            (master_id, day.isoformat(), _fmt(start), _fmt(end), reason),
        )

    async def list_time_off(self, master_id: int, from_date: dt.date) -> list[TimeOff]:
        rows = await self._db.fetch_all(
            "SELECT * FROM time_off WHERE master_id = ? AND date >= ? ORDER BY date, start_time",
            (master_id, from_date.isoformat()),
        )
        return [TimeOff.from_row(r) for r in rows]

    async def time_off_in_range(
        self,
        master_id: int,
        first: dt.date,
        last: dt.date,
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> list[TimeOff]:
        rows = await self._db.fetch_all(
            "SELECT * FROM time_off WHERE master_id = ? AND date BETWEEN ? AND ?",
            (master_id, first.isoformat(), last.isoformat()),
            conn=conn,
        )
        return [TimeOff.from_row(r) for r in rows]

    async def delete_time_off(self, time_off_id: int) -> None:
        await self._db.execute("DELETE FROM time_off WHERE id = ?", (time_off_id,))
