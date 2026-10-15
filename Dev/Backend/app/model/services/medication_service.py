"""PB-03: turn medication schedules into real doses (rows in medication_reminders).

A schedule says "08:00 local time, every day". This service creates one row per real
dose for the next few days, with due_at saved in UTC.

Safe to run again and again: the unique index (schedule_id, due_at) together with
ON CONFLICT DO NOTHING means the same dose is never created twice.

It will be called by: the reminder worker once a day, when a medication is
added, and the seed script. It does NOT commit; the caller does.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.model.entities import Medication, MedicationReminder, MedicationSchedule, User


def dose_times(
    time_of_day: time,
    days_of_week: Sequence[int],
    tz: ZoneInfo,
    first_day: date,
    days: int,
) -> list[datetime]:
    """UTC moments of every dose, for `days` local calendar days starting at first_day.

    zoneinfo handles daylight saving, so 08:00 stays 08:00 local time all year.
    Rare cases: a time that doesn't exist (02:30 on the spring-forward day) moves one
    hour later; a time that happens twice (01:30 on the fall-back day) uses the first.
    """
    result = []
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        if day.weekday() in days_of_week:  # 0 = Monday ... 6 = Sunday
            local = datetime.combine(day, time_of_day, tzinfo=tz)
            result.append(local.astimezone(UTC))
    return result


def generate_doses(
    db: DbSession,
    now: datetime,
    days: int | None = None,
    user_id: uuid.UUID | None = None,
) -> int:
    """Create the missing FUTURE doses for active medications. Returns how many were added.

    days: how many local days ahead (default: settings.medication_days_ahead).
    user_id: only this person's medications (default: everyone).
    """
    days = days or settings.medication_days_ahead

    # Every schedule of every medication that is not stopped, with its owner's time zone.
    query = (
        select(MedicationSchedule, Medication.user_id, User.timezone)
        .join(Medication, MedicationSchedule.medication_id == Medication.id)
        .join(User, Medication.user_id == User.id)
        .where(Medication.stopped_at.is_(None))
    )
    if user_id is not None:
        query = query.where(Medication.user_id == user_id)

    rows = []
    for schedule, owner_id, timezone_name in db.execute(query):
        tz = ZoneInfo(timezone_name)
        today = now.astimezone(tz).date()  # "today" in the USER's time zone
        for due_at in dose_times(schedule.time_of_day, schedule.days_of_week, tz, today, days):
            if due_at > now:  # never create doses in the past
                rows.append(
                    {
                        "id": uuid.uuid4(),
                        "schedule_id": schedule.id,
                        "user_id": owner_id,
                        "due_at": due_at,
                        "status": "scheduled",
                        "attempts": 0,
                    }
                )
    if not rows:
        return 0

    # One INSERT for all rows. Doses that already exist are skipped, not duplicated.
    # RETURNING gives back only the rows really added, so we can count them.
    statement = (
        insert(MedicationReminder)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["schedule_id", "due_at"])
        .returning(MedicationReminder.id)
    )
    return len(db.execute(statement).all())
