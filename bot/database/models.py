"""Plain typed records returned by repositories."""
import datetime as dt
import sqlite3
from dataclasses import dataclass

from bot.utils.dates import format_minutes, to_minutes


def _minutes(value: str) -> int:
    result = to_minutes(value)
    if result is None:
        raise ValueError(f"Invalid time stored in database: {value!r}")
    return result


def _optional_minutes(value: str | None) -> int | None:
    return None if value is None else _minutes(value)


@dataclass(frozen=True, slots=True)
class User:
    tg_id: int
    full_name: str
    username: str | None
    contact_name: str | None
    phone: str | None
    is_blocked: bool

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "User":
        return cls(
            tg_id=row["tg_id"],
            full_name=row["full_name"],
            username=row["username"],
            contact_name=row["contact_name"],
            phone=row["phone"],
            is_blocked=bool(row["is_blocked"]),
        )


@dataclass(frozen=True, slots=True)
class Service:
    id: int
    name: str
    price: int
    duration_min: int
    is_active: bool

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Service":
        return cls(
            id=row["id"],
            name=row["name"],
            price=row["price"],
            duration_min=row["duration_min"],
            is_active=bool(row["is_active"]),
        )


@dataclass(frozen=True, slots=True)
class Master:
    id: int
    name: str
    is_active: bool

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Master":
        return cls(id=row["id"], name=row["name"], is_active=bool(row["is_active"]))


@dataclass(frozen=True, slots=True)
class WorkDay:
    """Working hours of a master on one weekday (minutes from midnight)."""

    start: int
    end: int
    break_start: int | None = None
    break_end: int | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "WorkDay":
        return cls(
            start=_minutes(row["start_time"]),
            end=_minutes(row["end_time"]),
            break_start=_optional_minutes(row["break_start"]),
            break_end=_optional_minutes(row["break_end"]),
        )

    def describe(self) -> str:
        text = f"{format_minutes(self.start)}–{format_minutes(self.end)}"
        if self.break_start is not None and self.break_end is not None:
            text += f" (перерва {format_minutes(self.break_start)}–{format_minutes(self.break_end)})"
        return text


@dataclass(frozen=True, slots=True)
class TimeOff:
    """A closed day (start/end are None) or a closed time range."""

    id: int
    master_id: int
    date: dt.date
    start_min: int | None
    end_min: int | None
    reason: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "TimeOff":
        return cls(
            id=row["id"],
            master_id=row["master_id"],
            date=dt.date.fromisoformat(row["date"]),
            start_min=_optional_minutes(row["start_time"]),
            end_min=_optional_minutes(row["end_time"]),
            reason=row["reason"],
        )

    @property
    def is_whole_day(self) -> bool:
        return self.start_min is None or self.end_min is None


@dataclass(frozen=True, slots=True)
class Appointment:
    id: int
    user_tg_id: int | None
    service_id: int
    master_id: int
    date: dt.date
    start_min: int
    end_min: int
    client_name: str
    client_phone: str
    price: int
    duration_min: int
    status: str
    created_by: str
    service_name: str
    master_name: str
    reminder_24h_sent: bool
    reminder_2h_sent: bool

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Appointment":
        return cls(
            id=row["id"],
            user_tg_id=row["user_tg_id"],
            service_id=row["service_id"],
            master_id=row["master_id"],
            date=dt.date.fromisoformat(row["date"]),
            start_min=_minutes(row["start_time"]),
            end_min=_minutes(row["end_time"]),
            client_name=row["client_name"],
            client_phone=row["client_phone"],
            price=row["price"],
            duration_min=row["duration_min"],
            status=row["status"],
            created_by=row["created_by"],
            service_name=row["service_name"],
            master_name=row["master_name"],
            reminder_24h_sent=bool(row["reminder_24h_sent"]),
            reminder_2h_sent=bool(row["reminder_2h_sent"]),
        )

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def starts_at(self) -> dt.datetime:
        """Naive datetime in salon-local time."""
        return dt.datetime.combine(self.date, dt.time()) + dt.timedelta(minutes=self.start_min)
