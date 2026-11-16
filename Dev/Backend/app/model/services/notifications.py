"""Every reminder type, for the worker and the notification feed (plan §6.3, §6.4)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.model.entities import User

from .appointment_reminders import AppointmentReminderSource
from .reminder_source import Notification, ReminderSource

appointment_reminders = AppointmentReminderSource()

# PB-03 (S2-06): add the medication reminder source here.
SOURCES: list[ReminderSource] = [appointment_reminders]

FEED_WINDOW = timedelta(hours=12)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def recent_notifications(
    session: Session, user: User, *, clock: Callable[[], datetime] | None = None
) -> list[Notification]:
    """Reminders of every kind that came due in the last 12 hours, oldest first."""
    now = (clock or _utcnow)()
    items = [
        item
        for source in SOURCES
        for item in source.recent_for_user(session, user, now - FEED_WINDOW, now)
    ]
    return sorted(items, key=lambda item: item.due_at)
