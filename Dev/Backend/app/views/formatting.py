"""Dates and times as the user hears them, in the user's own time zone (plan §6.5).

Avoids strftime flags like %-d that don't exist on Windows.
"""

from datetime import datetime
from zoneinfo import ZoneInfo


def spoken_date(moment: datetime, timezone: str) -> str:
    """'Tuesday, October 20'"""
    local = moment.astimezone(ZoneInfo(timezone))
    return f"{local:%A, %B} {local.day}"


def spoken_time(moment: datetime, timezone: str) -> str:
    """'10:30 AM'"""
    local = moment.astimezone(ZoneInfo(timezone))
    return local.strftime("%I:%M %p").lstrip("0")


def spoken_date_time(moment: datetime, timezone: str) -> str:
    """'Tuesday, October 20 at 10:30 AM'"""
    return f"{spoken_date(moment, timezone)} at {spoken_time(moment, timezone)}"


def spoken_list(items: list[str]) -> str:
    """'a', 'a or b', 'a, b, or c'"""
    if len(items) <= 2:
        return " or ".join(items)
    return f"{', '.join(items[:-1])}, or {items[-1]}"
