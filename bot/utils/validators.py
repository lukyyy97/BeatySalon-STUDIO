"""Validation / normalisation of text typed by users and admins."""
import re

from bot.utils.dates import to_minutes

_PHONE_CLEAN_RE = re.compile(r"[\s\-().]")
_NAME_ALLOWED_SYMBOLS = set(" -'’ʼ.")
_RANGE_RE = re.compile(r"(\d{1,2}[:.]\d{2})\s*[-–—]\s*(\d{1,2}[:.]\d{2})")


def normalize_phone(raw: str) -> str | None:
    """Normalise a typed phone number to E.164-like '+380XXXXXXXXX'. None if invalid."""
    cleaned = _PHONE_CLEAN_RE.sub("", raw.strip())
    if not re.fullmatch(r"\+?[0-9]{10,15}", cleaned):
        return None
    if cleaned.startswith("+"):
        digits = cleaned[1:]
        if digits.startswith("380") and len(digits) != 12:
            return None
        return "+" + digits
    if len(cleaned) == 10 and cleaned.startswith("0"):
        return "+38" + cleaned
    if len(cleaned) == 12 and cleaned.startswith("380"):
        return "+" + cleaned
    return None


def normalize_contact_phone(raw: str) -> str | None:
    """Phone number from a Telegram contact (may come without '+')."""
    digits = re.sub(r"\D", "", raw)
    return "+" + digits if 10 <= len(digits) <= 15 else None


def validate_name(raw: str) -> str | None:
    """Person name: 2-50 chars, letters plus space/hyphen/apostrophe/dot."""
    name = " ".join(raw.split())
    if not 2 <= len(name) <= 50:
        return None
    if not all(ch.isalpha() or ch in _NAME_ALLOWED_SYMBOLS for ch in name):
        return None
    if not any(ch.isalpha() for ch in name):
        return None
    return name


def clean_title(raw: str, max_len: int = 60) -> str | None:
    """Free-form title (service / master name)."""
    title = " ".join(raw.split())
    return title if 2 <= len(title) <= max_len else None


def parse_int_in_range(raw: str, low: int, high: int) -> int | None:
    cleaned = re.sub(r"(грн|₴|хв|min|\s)", "", raw.strip().lower())
    if not re.fullmatch(r"[0-9]+", cleaned):
        return None
    value = int(cleaned)
    return value if low <= value <= high else None


def parse_price(raw: str) -> int | None:
    return parse_int_in_range(raw, 0, 1_000_000)


def parse_duration(raw: str) -> int | None:
    return parse_int_in_range(raw, 5, 720)


def parse_time_range(raw: str) -> tuple[int, int] | None:
    """'13:00-15:00' -> (780, 900)."""
    match = _RANGE_RE.fullmatch(raw.strip())
    if match is None:
        return None
    start, end = to_minutes(match.group(1)), to_minutes(match.group(2))
    if start is None or end is None or start >= end:
        return None
    return start, end


def parse_work_hours(raw: str) -> tuple[int, int, int | None, int | None] | None:
    """'09:00-18:00' or '09:00-18:00 13:00-14:00' (work hours + optional break)."""
    ranges = _RANGE_RE.findall(raw)
    if not 1 <= len(ranges) <= 2:
        return None
    parsed: list[tuple[int, int]] = []
    for first, second in ranges:
        start, end = to_minutes(first), to_minutes(second)
        if start is None or end is None or start >= end:
            return None
        parsed.append((start, end))
    start, end = parsed[0]
    if len(parsed) == 1:
        return start, end, None, None
    break_start, break_end = parsed[1]
    if not (start <= break_start and break_end <= end):
        return None
    return start, end, break_start, break_end
