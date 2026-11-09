"""Dose generator (PB-03): local times -> UTC doses, daylight saving, no duplicates."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.model.entities import Medication, MedicationReminder, MedicationSchedule, User
from app.model.entities.medication import EVERY_DAY
from app.model.services.medication_service import dose_times, generate_doses

LA = ZoneInfo("America/Los_Angeles")


def la(month: int, day: int, hour: int, minute: int = 0, year: int = 2026) -> datetime:
    """A time in California."""
    return datetime(year, month, day, hour, minute, tzinfo=LA)


# ---------- dose_times: pure calculation, no database ----------


def test_daily_8am_becomes_utc():
    times = dose_times(time(8, 0), EVERY_DAY, LA, date(2026, 10, 19), 3)
    assert times == [
        datetime(2026, 10, 19, 15, 0, tzinfo=UTC),  # 8:00 PDT = 15:00 UTC
        datetime(2026, 10, 20, 15, 0, tzinfo=UTC),
        datetime(2026, 10, 21, 15, 0, tzinfo=UTC),
    ]


def test_8am_stays_8am_after_daylight_saving_ends():
    # Daylight saving ends Sunday, Nov 1, 2026: UTC time moves, local time does not.
    times = dose_times(time(8, 0), EVERY_DAY, LA, date(2026, 10, 31), 3)
    assert [t.astimezone(LA).hour for t in times] == [8, 8, 8]
    assert [t.hour for t in times] == [15, 16, 16]  # UTC


def test_only_chosen_days():
    mondays = dose_times(time(9, 0), [0], LA, date(2026, 10, 19), 14)  # Oct 19 = Monday
    assert [t.astimezone(LA).date() for t in mondays] == [date(2026, 10, 19), date(2026, 10, 26)]


def test_time_that_does_not_exist_moves_one_hour_later():
    # Mar 14, 2027: clocks jump from 02:00 to 03:00, so 02:30 doesn't exist.
    [t] = dose_times(time(2, 30), EVERY_DAY, LA, date(2027, 3, 14), 1)
    assert t.astimezone(LA).time() == time(3, 30)


# ---------- generate_doses: with the test database ----------


def make_medication(db, times=("08:00", "20:00"), user=None, **fields) -> Medication:
    """Margaret-like user with one medication taken at the given local times."""
    if user is None:
        user = User(role="older_adult", display_name="Test Person")
        db.add(user)
        db.flush()  # gives the user an id
    medication = Medication(user_id=user.id, name="Metformin", dosage="500 mg", **fields)
    medication.schedules = [
        MedicationSchedule(time_of_day=time.fromisoformat(t), days_of_week=list(EVERY_DAY))
        for t in times
    ]
    db.add(medication)
    db.flush()
    return medication


def count_doses(db) -> int:
    return db.scalar(select(func.count()).select_from(MedicationReminder))


def test_creates_one_week_of_doses(db):
    make_medication(db)  # 08:00 and 20:00
    added = generate_doses(db, now=la(10, 18, 6), days=7)  # Sunday 06:00
    assert added == 14  # 2 per day x 7 days
    first = db.scalar(select(MedicationReminder).order_by(MedicationReminder.due_at))
    assert first.due_at == la(10, 18, 8)
    assert first.status == "scheduled"
    assert first.attempts == 0


def test_running_twice_adds_nothing_new(db):
    make_medication(db)
    generate_doses(db, now=la(10, 18, 6), days=7)
    assert generate_doses(db, now=la(10, 18, 6), days=7) == 0
    assert count_doses(db) == 14


def test_past_doses_are_skipped(db):
    make_medication(db)
    assert generate_doses(db, now=la(10, 18, 12), days=7) == 13  # today's 08:00 is past


def test_stopped_medication_gets_no_doses(db):
    make_medication(db, stopped_at=la(10, 17, 9))
    assert generate_doses(db, now=la(10, 18, 6), days=7) == 0


def test_only_one_users_medications(db):
    mine = make_medication(db, times=("08:00",))
    make_medication(db, times=("09:00",))  # someone else
    assert generate_doses(db, now=la(10, 18, 6), days=7, user_id=mine.user_id) == 7


def test_uses_the_users_own_time_zone(db):
    user = User(role="older_adult", display_name="New Yorker", timezone="America/New_York")
    db.add(user)
    db.flush()
    make_medication(db, times=("08:00",), user=user)
    generate_doses(db, now=la(10, 18, 3), days=1)  # 03:00 in LA = 06:00 in New York
    dose = db.scalar(select(MedicationReminder))
    assert dose.due_at == datetime(2026, 10, 18, 12, 0, tzinfo=UTC)  # 08:00 EDT


# ---------- Database rules ----------


def test_database_blocks_a_duplicate_dose(db):
    schedule = make_medication(db, times=("08:00",)).schedules[0]
    for _ in range(2):
        db.add(
            MedicationReminder(
                schedule_id=schedule.id, user_id=schedule.medication.user_id, due_at=la(10, 19, 8)
            )
        )
    with pytest.raises(IntegrityError):
        db.flush()


def test_database_needs_confirmed_at_for_taken(db):
    schedule = make_medication(db, times=("08:00",)).schedules[0]
    db.add(
        MedicationReminder(
            schedule_id=schedule.id,
            user_id=schedule.medication.user_id,
            due_at=la(10, 19, 8),
            status="taken",  # but no confirmed_at
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
