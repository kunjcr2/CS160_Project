"""Medication doses after creation (PB-03): sent, re-prompt, missed, taken."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.model.entities import Medication, MedicationReminder, MedicationSchedule, User
from app.model.services.medication_reminders import (
    MedicationReminderSource,
    ReminderNotChangeableError,
    ReminderNotFoundError,
    mark_missed,
    mark_taken,
)

LA = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 10, 19, 8, 0, tzinfo=LA)  # Monday 08:00 in California
source = MedicationReminderSource()


def minutes(n: int) -> timedelta:
    return timedelta(minutes=n)


def make_user(db, name: str = "Test Person") -> User:
    user = User(role="older_adult", display_name=name)
    db.add(user)
    db.flush()
    return user


def make_dose(db, due_at=NOW, user=None, stopped_at=None, **fields) -> MedicationReminder:
    """One dose of a test medication. Extra fields (status, sent_at, ...) go on the dose."""
    user = user or make_user(db)
    medication = Medication(user_id=user.id, name="Metformin", dosage="500 mg")
    medication.stopped_at = stopped_at
    schedule = MedicationSchedule(time_of_day=time(8, 0), days_of_week=[0, 1, 2, 3, 4, 5, 6])
    medication.schedules = [schedule]
    db.add(medication)
    db.flush()
    dose = MedicationReminder(schedule_id=schedule.id, user_id=user.id, due_at=due_at, **fields)
    db.add(dose)
    db.flush()
    return dose


def sent_dose(db, sent_minutes_ago: int, attempts: int = 1, **fields) -> MedicationReminder:
    sent_at = NOW - minutes(sent_minutes_ago)
    return make_dose(
        db, due_at=sent_at, status="sent", sent_at=sent_at, attempts=attempts, **fields
    )


# ---------- send_due ----------


def test_due_dose_is_sent(db):
    dose = make_dose(db)
    assert source.send_due(db, NOW) == 1
    assert (dose.status, dose.sent_at, dose.attempts) == ("sent", NOW, 1)


def test_future_dose_is_not_sent(db):
    dose = make_dose(db, due_at=NOW + minutes(1))
    assert source.send_due(db, NOW) == 0
    assert dose.status == "scheduled"


def test_sending_twice_sends_once(db):
    make_dose(db)
    source.send_due(db, NOW)
    assert source.send_due(db, NOW) == 0


def test_dose_of_stopped_medication_is_cancelled(db):
    dose = make_dose(db, stopped_at=NOW - minutes(60))
    assert source.send_due(db, NOW) == 0
    assert dose.status == "cancelled"


def test_very_late_dose_is_failed_not_sent(db):
    dose = make_dose(db, due_at=NOW - minutes(120))  # the worker was down for 2 hours
    assert source.send_due(db, NOW) == 0
    assert dose.status == "failed"


# ---------- follow_up: re-prompt once, then missed ----------


def test_no_follow_up_before_30_minutes(db):
    dose = sent_dose(db, sent_minutes_ago=10)
    assert source.follow_up(db, NOW) == 0
    assert (dose.status, dose.attempts) == ("sent", 1)


def test_reprompt_after_30_minutes(db):
    dose = sent_dose(db, sent_minutes_ago=30)
    assert source.follow_up(db, NOW) == 1
    assert (dose.status, dose.attempts) == ("sent", 2)


def test_reprompt_happens_only_once(db):
    dose = sent_dose(db, sent_minutes_ago=40, attempts=2)
    assert source.follow_up(db, NOW) == 0
    assert (dose.status, dose.attempts) == ("sent", 2)


def test_missed_after_60_minutes(db):
    dose = sent_dose(db, sent_minutes_ago=60, attempts=2)
    assert source.follow_up(db, NOW) == 1
    assert (dose.status, dose.confirmed_at) == ("missed", NOW)


# ---------- mark_taken / mark_missed ----------


def test_taken(db):
    dose = sent_dose(db, sent_minutes_ago=5)
    user = db.get(User, dose.user_id)
    mark_taken(db, dose.id, user, NOW)
    assert (dose.status, dose.confirmed_at) == ("taken", NOW)


def test_taken_twice_is_fine(db):
    dose = sent_dose(db, sent_minutes_ago=5)
    user = db.get(User, dose.user_id)
    mark_taken(db, dose.id, user, NOW)
    mark_taken(db, dose.id, user, NOW + minutes(1))
    assert (dose.status, dose.confirmed_at) == ("taken", NOW)  # first answer kept


def test_missed_can_be_corrected_to_taken(db):
    dose = make_dose(db, status="missed", confirmed_at=NOW - minutes(5))
    mark_taken(db, dose.id, db.get(User, dose.user_id), NOW)
    assert dose.status == "taken"


def test_someone_elses_dose_is_not_found(db):
    dose = sent_dose(db, sent_minutes_ago=5)
    stranger = make_user(db, "Stranger")
    with pytest.raises(ReminderNotFoundError):
        mark_taken(db, dose.id, stranger, NOW)
    assert dose.status == "sent"


def test_too_early_to_answer(db):
    dose = make_dose(db, due_at=NOW + timedelta(hours=3))
    with pytest.raises(ReminderNotChangeableError) as error:
        mark_taken(db, dose.id, db.get(User, dose.user_id), NOW)
    assert error.value.code == "too_early"


def test_cancelled_dose_cannot_be_taken(db):
    dose = make_dose(db, status="cancelled")
    with pytest.raises(ReminderNotChangeableError) as error:
        mark_taken(db, dose.id, db.get(User, dose.user_id), NOW)
    assert error.value.code == "cancelled"


def test_user_says_missed(db):
    dose = sent_dose(db, sent_minutes_ago=5)
    mark_missed(db, dose.id, db.get(User, dose.user_id), NOW)
    assert (dose.status, dose.confirmed_at) == ("missed", NOW)


def test_taken_dose_cannot_become_missed(db):
    dose = make_dose(db, status="taken", confirmed_at=NOW)
    with pytest.raises(ReminderNotChangeableError) as error:
        mark_missed(db, dose.id, db.get(User, dose.user_id), NOW)
    assert error.value.code == "taken"
