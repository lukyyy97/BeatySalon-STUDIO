import datetime as dt

from bot.utils.dates import (
    find_dates,
    format_date_long,
    format_duration,
    format_minutes,
    parse_iso_date,
    to_minutes,
)
from bot.utils.validators import (
    normalize_contact_phone,
    normalize_phone,
    parse_duration,
    parse_price,
    parse_time_range,
    parse_work_hours,
    validate_name,
)


def test_minutes_roundtrip():
    assert to_minutes("09:30") == 570
    assert to_minutes("9.05") == 545
    assert to_minutes("24:00") is None
    assert to_minutes("abc") is None
    assert format_minutes(570) == "09:30"


def test_format_helpers():
    assert format_duration(90) == "1 год 30 хв"
    assert format_duration(45) == "45 хв"
    assert format_duration(120) == "2 год"
    assert format_date_long(dt.date(2026, 11, 24)) == "24 листопада 2026, вівторок"
    assert parse_iso_date("2026-11-24") == dt.date(2026, 11, 24)
    assert parse_iso_date("nonsense") is None


def test_find_dates():
    today = dt.date(2026, 11, 23)
    assert find_dates("25.12.2026", today) == [dt.date(2026, 12, 25)]
    assert find_dates("25.12", today) == [dt.date(2026, 12, 25)]
    assert find_dates("25.12.2026-31.12.2026", today) == [dt.date(2026, 12, 25), dt.date(2026, 12, 31)]
    assert find_dates("31.02.2026", today) is None
    assert find_dates("hello", today) == []


def test_phone_normalisation():
    assert normalize_phone("0501234567") == "+380501234567"
    assert normalize_phone("+38 (050) 123-45-67") == "+380501234567"
    assert normalize_phone("380501234567") == "+380501234567"
    assert normalize_phone("+4915112345678") == "+4915112345678"
    assert normalize_phone("12345") is None
    assert normalize_phone("+3805012345") is None  # wrong length for Ukraine
    assert normalize_phone("abc") is None
    assert normalize_contact_phone("380501234567") == "+380501234567"
    assert normalize_contact_phone("12") is None


def test_name_validation():
    assert validate_name("  Олена  ") == "Олена"
    assert validate_name("Марія-Ізабелла О’Нілл") == "Марія-Ізабелла О’Нілл"
    assert validate_name("A") is None
    assert validate_name("Олена123") is None
    assert validate_name("<b>Hack</b>") is None


def test_numbers_and_hours():
    assert parse_price("600") == 600
    assert parse_price("600 грн") == 600
    assert parse_price("-5") is None
    assert parse_duration("60") == 60
    assert parse_duration("3") is None
    assert parse_time_range("13:00-15:00") == (780, 900)
    assert parse_time_range("15:00-13:00") is None
    assert parse_work_hours("09:00-18:00") == (540, 1080, None, None)
    assert parse_work_hours("09:00-18:00 13:00-14:00") == (540, 1080, 780, 840)
    assert parse_work_hours("09:00-18:00 07:00-08:00") is None  # break outside the work day
    assert parse_work_hours("nope") is None
