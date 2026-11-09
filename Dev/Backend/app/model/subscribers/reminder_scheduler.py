"""PB-02: create appointment reminders when an appointment is booked; cancel them when it
is cancelled (Observer, plan §4, §8 PB-02). The appointment code never calls this directly.

Reminder times are worked out on the user's LOCAL clock with zoneinfo and stored in UTC
(plan §6.5). "The day before at the same time" is a local wall-clock time, so it stays
right across a daylight-saving change; subtracting 24 hours in UTC would not.
"""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.model.entities import Appointment, AppointmentReminder, User
from app.model.events import AppointmentBooked, AppointmentCancelled

MORNING_OF = time(8, 0)  # local time on the day of the appointment


def _utcnow() -> datetime:
    return datetime.now(UTC)


def reminder_times(starts_at: datetime, timezone: str) -> dict[str, datetime]:
    """When each reminder is due (UTC) for an appointment starting at `starts_at`.

    - day_before: the same local time on the previous day
    - morning_of: 8:00 AM local on the day, only if that is before hour_before
    - hour_before: one hour before the start
    """
    tz = ZoneInfo(timezone)
    local_start = starts_at.astimezone(tz)
    day_before = datetime.combine(local_start.date() - timedelta(days=1), local_start.time(), tz)
    morning_of = datetime.combine(local_start.date(), MORNING_OF, tz)
    hour_before = starts_at - timedelta(hours=1)

    times = {"day_before": day_before.astimezone(UTC)}
    if morning_of < hour_before:
        times["morning_of"] = morning_of.astimezone(UTC)
    times["hour_before"] = hour_before.astimezone(UTC)
    return times


def on_appointment_booked(session: Session, event: AppointmentBooked) -> None:
    appointment = session.get(Appointment, event.appointment_id)
    user = session.get(User, appointment.user_id)
    now = _utcnow()
    rows = [
        {
            "appointment_id": appointment.id,
            "user_id": appointment.user_id,
            "kind": kind,
            "due_at": due_at,
            "status": "scheduled",
            "attempts": 0,
        }
        for kind, due_at in reminder_times(appointment.starts_at, user.timezone).items()
        if due_at > now  # booked late: skip reminders whose time has passed
    ]
    if rows:
        # The unique (appointment_id, kind) index makes running this twice harmless.
        session.execute(
            insert(AppointmentReminder)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["appointment_id", "kind"])
        )


def on_appointment_cancelled(session: Session, event: AppointmentCancelled) -> None:
    session.execute(
        update(AppointmentReminder)
        .where(
            AppointmentReminder.appointment_id == event.appointment_id,
            AppointmentReminder.status == "scheduled",
        )
        .values(status="cancelled")
    )
