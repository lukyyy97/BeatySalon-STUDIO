import datetime as dt

import aiosqlite

from bot.database.db import Database
from bot.database.models import Appointment
from bot.utils.dates import format_minutes, to_minutes

_SELECT = """
    SELECT a.*, s.name AS service_name, m.name AS master_name
    FROM appointments a
    JOIN services s ON s.id = a.service_id
    JOIN masters  m ON m.id = a.master_id
"""

_REMINDER_COLUMNS = {"24h": "reminder_24h_sent", "2h": "reminder_2h_sent"}


class AppointmentRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def get(self, appointment_id: int, *, conn: aiosqlite.Connection | None = None) -> Appointment | None:
        row = await self._db.fetch_one(_SELECT + " WHERE a.id = ?", (appointment_id,), conn=conn)
        return Appointment.from_row(row) if row else None

    async def insert(
        self,
        conn: aiosqlite.Connection,
        *,
        user_tg_id: int | None,
        service_id: int,
        master_id: int,
        day: dt.date,
        start_min: int,
        end_min: int,
        client_name: str,
        client_phone: str,
        price: int,
        duration_min: int,
        created_by: str,
        reminder_24h_sent: bool,
        reminder_2h_sent: bool,
    ) -> int:
        return await self._db.insert(
            """
            INSERT INTO appointments (
                user_tg_id, service_id, master_id, date, start_time, end_time,
                client_name, client_phone, price, duration_min, created_by,
                reminder_24h_sent, reminder_2h_sent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_tg_id, service_id, master_id, day.isoformat(),
                format_minutes(start_min), format_minutes(end_min),
                client_name, client_phone, price, duration_min, created_by,
                int(reminder_24h_sent), int(reminder_2h_sent),
            ),
            conn=conn,
        )

    async def cancel(
        self, appointment_id: int, cancelled_by: str, *, conn: aiosqlite.Connection | None = None
    ) -> bool:
        """Mark an active appointment as cancelled. Returns False if it was not active."""
        affected = await self._db.execute(
            """
            UPDATE appointments
            SET status = 'cancelled', cancelled_by = ?, cancelled_at = datetime('now')
            WHERE id = ? AND status = 'active'
            """,
            (cancelled_by, appointment_id),
            conn=conn,
        )
        return affected > 0

    async def upcoming_for_user(self, tg_id: int, now: dt.datetime) -> list[Appointment]:
        today = now.date().isoformat()
        clock = format_minutes(now.hour * 60 + now.minute)
        rows = await self._db.fetch_all(
            _SELECT
            + """
            WHERE a.user_tg_id = ? AND a.status = 'active'
              AND (a.date > ? OR (a.date = ? AND a.end_time > ?))
            ORDER BY a.date, a.start_time
            """,
            (tg_id, today, today, clock),
        )
        return [Appointment.from_row(r) for r in rows]

    async def for_day(self, day: dt.date, master_id: int | None = None) -> list[Appointment]:
        sql = _SELECT + " WHERE a.date = ? AND a.status = 'active'"
        params: list[object] = [day.isoformat()]
        if master_id:
            sql += " AND a.master_id = ?"
            params.append(master_id)
        rows = await self._db.fetch_all(sql + " ORDER BY a.start_time, a.id", params)
        return [Appointment.from_row(r) for r in rows]

    async def busy_in_range(
        self,
        master_id: int,
        first: dt.date,
        last: dt.date,
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> dict[dt.date, list[tuple[int, int]]]:
        """Occupied intervals (minutes) of a master per date, active appointments only."""
        rows = await self._db.fetch_all(
            """
            SELECT date, start_time, end_time FROM appointments
            WHERE master_id = ? AND status = 'active' AND date BETWEEN ? AND ?
            """,
            (master_id, first.isoformat(), last.isoformat()),
            conn=conn,
        )
        result: dict[dt.date, list[tuple[int, int]]] = {}
        for row in rows:
            start, end = to_minutes(row["start_time"]), to_minutes(row["end_time"])
            if start is None or end is None:
                continue
            result.setdefault(dt.date.fromisoformat(row["date"]), []).append((start, end))
        return result

    async def overlapping(
        self, master_id: int, day: dt.date, start_min: int, end_min: int
    ) -> list[Appointment]:
        """Active appointments of a master that intersect the given interval."""
        rows = await self._db.fetch_all(
            _SELECT
            + """
            WHERE a.master_id = ? AND a.date = ? AND a.status = 'active'
              AND a.start_time < ? AND a.end_time > ?
            ORDER BY a.start_time
            """,
            (master_id, day.isoformat(), format_minutes(end_min), format_minutes(start_min)),
        )
        return [Appointment.from_row(r) for r in rows]

    async def due_for_reminders(self, first: dt.date, last: dt.date) -> list[Appointment]:
        """Active, bot-linked appointments in [first, last] that still await a reminder."""
        rows = await self._db.fetch_all(
            _SELECT
            + """
            WHERE a.status = 'active' AND a.user_tg_id IS NOT NULL
              AND a.date BETWEEN ? AND ?
              AND (a.reminder_24h_sent = 0 OR a.reminder_2h_sent = 0)
            ORDER BY a.date, a.start_time
            """,
            (first.isoformat(), last.isoformat()),
        )
        return [Appointment.from_row(r) for r in rows]

    async def mark_reminder_sent(self, appointment_id: int, kind: str) -> None:
        column = _REMINDER_COLUMNS[kind]
        await self._db.execute(
            f"UPDATE appointments SET {column} = 1 WHERE id = ?", (appointment_id,)  # noqa: S608
        )

    async def count_upcoming(self, now: dt.datetime) -> int:
        today = now.date().isoformat()
        clock = format_minutes(now.hour * 60 + now.minute)
        row = await self._db.fetch_one(
            """
            SELECT COUNT(*) AS n FROM appointments
            WHERE status = 'active' AND (date > ? OR (date = ? AND end_time > ?))
            """,
            (today, today, clock),
        )
        return int(row["n"]) if row else 0
