"""Date/time helpers: Ukrainian formatting and lenient parsing of user input."""
import datetime as dt
import re

WEEKDAYS = ("понеділок", "вівторок", "середа", "четвер", "п’ятниця", "субота", "неділя")
WEEKDAYS_SHORT = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд")
WEEKDAYS_FULL = ("Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя")
MONTHS_GEN = (
    "січня", "лютого", "березня", "квітня", "травня", "червня",
    "липня", "серпня", "вересня", "жовтня", "листопада", "грудня",
)

_TIME_RE = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*$")
_DATE_TOKEN_RE = re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})(?:[./](\d{4}|\d{2}))?(?!\d)")


def to_minutes(value: str) -> int | None:
    """'09:30' -> 570. Returns None for invalid input."""
    match = _TIME_RE.match(value)
    if match is None:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        return None
    return hours * 60 + minutes


def format_minutes(total: int) -> str:
    """570 -> '09:30'."""
    return f"{total // 60:02d}:{total % 60:02d}"


def format_time_range(start: int, end: int) -> str:
    return f"{format_minutes(start)}–{format_minutes(end)}"


def format_date_long(day: dt.date) -> str:
    """'24 листопада 2026, вівторок'."""
    return f"{day.day} {MONTHS_GEN[day.month - 1]} {day.year}, {WEEKDAYS[day.weekday()]}"


def format_date_short(day: dt.date) -> str:
    return f"{day:%d.%m.%Y}"


def format_date_button(day: dt.date) -> str:
    """'Вт 24.11'."""
    return f"{WEEKDAYS_SHORT[day.weekday()]} {day:%d.%m}"


def format_duration(minutes: int) -> str:
    """90 -> '1 год 30 хв'."""
    hours, rest = divmod(minutes, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} год")
    if rest:
        parts.append(f"{rest} хв")
    return " ".join(parts) or "0 хв"


def parse_iso_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def find_dates(text: str, today: dt.date) -> list[dt.date] | None:
    """Extract every dd.mm[.yyyy] date from text. Returns None if a token is not a real date."""
    result: list[dt.date] = []
    for match in _DATE_TOKEN_RE.finditer(text):
        day, month, year = int(match.group(1)), int(match.group(2)), match.group(3)
        if year is None:
            year_value = today.year
        elif len(year) == 4:
            year_value = int(year)
        else:
            year_value = 2000 + int(year)
        try:
            result.append(dt.date(year_value, month, day))
        except ValueError:
            return None
    return result
