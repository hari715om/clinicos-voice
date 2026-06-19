"""
Time utilities for ClinicOS Voice.

All timestamps are stored as UTC in PostgreSQL.
IST (Asia/Kolkata, UTC+5:30) is used for display, scheduling logic,
and slot generation — since Utkal Hospital operates on IST.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytz

IST = pytz.timezone("Asia/Kolkata")
UTC = pytz.UTC


def now_utc() -> datetime:
    """Return the current time as a UTC-aware datetime."""
    return datetime.now(UTC)


def now_ist() -> datetime:
    """Return the current time as an IST-aware datetime."""
    return datetime.now(IST)


def to_ist(dt: datetime) -> datetime:
    """Convert a UTC-aware datetime to IST."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(IST)


def to_utc(dt: datetime) -> datetime:
    """Convert an IST-naive or IST-aware datetime to UTC."""
    if dt.tzinfo is None:
        dt = IST.localize(dt)
    return dt.astimezone(UTC)


def ist_datetime(d: date, t: time) -> datetime:
    """Combine an IST date and time into a UTC-aware datetime."""
    naive = datetime.combine(d, t)
    return to_utc(IST.localize(naive))


def parse_date(date_str: str) -> date:
    """Parse a YYYY-MM-DD string into a date object."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def date_range(start: date, days: int) -> list[date]:
    """Return a list of consecutive dates starting from `start`."""
    return [start + timedelta(days=i) for i in range(days)]


def format_slot_for_voice(dt: datetime) -> str:
    """
    Format a slot datetime as a natural, voice-friendly IST string.
    Example: "Monday, 23 June at 10:30 AM"
    """
    ist_dt = to_ist(dt)
    return ist_dt.strftime("%A, %d %B at %I:%M %p")


def is_past(dt: datetime) -> bool:
    """Return True if the given datetime (UTC-aware) is in the past."""
    return dt < now_utc()


def hours_until(dt: datetime) -> float:
    """Return the number of hours between now and a future datetime."""
    delta = dt - now_utc()
    return delta.total_seconds() / 3600
