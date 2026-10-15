"""PB-03: turn medication schedules into real doses (rows in medication_reminders).

A schedule says "08:00 local time, every day". This service creates one row per real
dose for the next few days, with due_at saved in UTC.

Safe to run again and again: the unique index (schedule_id, due_at) together with
ON CONFLICT DO NOTHING means the same dose is never created twice.

It will be called by: the reminder worker once a day, when a medication is
added (create_medication below), and the seed script.

Also here: add a medication, list medications, and list one day's doses.
Nothing here commits; the caller does.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload

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


# ---------- Add and list medications (used by the endpoints) ----------


def create_medication(
    db: DbSession,
    older_adult_id: uuid.UUID,
    *,
    name: str,
    dosage: str,
    instructions: str | None,
    refills_remaining: int,
    schedules: list[tuple[time, list[int]]],
    now: datetime,
) -> Medication:
    """Add a medication with its schedule, then create its doses for the next days."""
    medication = Medication(
        user_id=older_adult_id,
        name=name,
        dosage=dosage,
        instructions=instructions,
        refills_remaining=refills_remaining,
    )
    medication.schedules = [
        MedicationSchedule(time_of_day=time_of_day, days_of_week=list(days))
        for time_of_day, days in schedules
    ]
    db.add(medication)
    db.flush()  # gives the medication and schedules their ids
    generate_doses(db, now, user_id=older_adult_id)
    return medication


def list_medications(db: DbSession, older_adult_id: uuid.UUID) -> list[Medication]:
    """All of one person's medications (stopped ones too), A to Z, with their schedules."""
    return list(
        db.scalars(
            select(Medication)
            .where(Medication.user_id == older_adult_id)
            .order_by(Medication.name)
            # selectinload: load every schedule in ONE extra query, not one per medication.
            .options(selectinload(Medication.schedules))
        )
    )


def doses_for_day(
    db: DbSession, older_adult_id: uuid.UUID, day: date
) -> list[tuple[MedicationReminder, Medication]]:
    """One person's doses on one LOCAL calendar day, in time order, with their medication."""
    tz = ZoneInfo(db.get(User, older_adult_id).timezone)
    day_start = datetime.combine(day, time(0, 0), tzinfo=tz)  # midnight, local time
    next_day_start = datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=tz)
    rows = db.execute(
        select(MedicationReminder, Medication)
        .join(MedicationSchedule, MedicationReminder.schedule_id == MedicationSchedule.id)
        .join(Medication, MedicationSchedule.medication_id == Medication.id)
        .where(
            MedicationReminder.user_id == older_adult_id,
            MedicationReminder.due_at >= day_start,
            MedicationReminder.due_at < next_day_start,
        )
        .order_by(MedicationReminder.due_at, Medication.name)
    )
    return [(reminder, medication) for reminder, medication in rows]
