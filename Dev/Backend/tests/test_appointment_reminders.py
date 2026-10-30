"""PB-02 appointment reminders (S2-11): reminders fire at the right local time; a cancelled
appointment gets no reminders."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from conftest import next_tuesday
from sqlalchemy import select

from app.model.entities import Appointment, AppointmentReminder
from app.model.events import AppointmentBooked, AppointmentCancelled, events
from app.model.services.action_service import ActionService
from app.model.services.appointment_service import AppointmentService
from app.model.subscribers.reminder_scheduler import on_appointment_booked, reminder_times
from app.workers.reminders import run_once

LA = "America/Los_Angeles"


@pytest.fixture(autouse=True)
def _fresh_provider(mock_provider):
    """Every test gets its own mock provider (see conftest)."""


def _reminders(db, appointment_id) -> dict[str, AppointmentReminder]:
    rows = db.scalars(
        select(AppointmentReminder).where(AppointmentReminder.appointment_id == appointment_id)
    )
    return {row.kind: row for row in rows}


def _book(db, user, provider) -> Appointment:
    """Book next Tuesday's first slot from 10 AM on (late enough for all three reminders)."""
    slots = AppointmentService(db).find_slots(
        user, provider, next_tuesday(), next_tuesday(), limit=20
    )
    slot = next(s for s in slots if s.starts_at.astimezone(ZoneInfo(LA)).hour >= 10)
    actions = ActionService(db)
    action = actions.propose(user, "book_appointment", {"slot_id": slot.slot_id})
    outcome = actions.confirm(action.id, user)
    db.commit()
    return db.get(Appointment, outcome.action.result["data"]["appointment_id"])


# --- When reminders are due (pure time arithmetic) --------------------------------------


def test_reminder_times_on_a_normal_day():
    starts_at = datetime(2026, 10, 20, 17, 30, tzinfo=UTC)  # Tue 10:30 AM PDT
    assert reminder_times(starts_at, LA) == {
        "day_before": datetime(2026, 10, 19, 17, 30, tzinfo=UTC),  # Mon 10:30 AM PDT
        "morning_of": datetime(2026, 10, 20, 15, 0, tzinfo=UTC),  # Tue 8:00 AM PDT
        "hour_before": datetime(2026, 10, 20, 16, 30, tzinfo=UTC),  # Tue 9:30 AM PDT
    }


def test_day_before_stays_on_local_time_when_daylight_saving_ends():
    """US daylight saving ends Sun Nov 1, 2026 at 2 AM. Appointment Sun 10:00 AM PST."""
    starts_at = datetime(2026, 11, 1, 18, 0, tzinfo=UTC)  # 10:00 AM PST
    times = reminder_times(starts_at, LA)

    # Sat Oct 31, 10:00 AM PDT. Naive "minus 24 h in UTC" would give 18:00 UTC = 11 AM.
    assert times["day_before"] == datetime(2026, 10, 31, 17, 0, tzinfo=UTC)
    assert times["morning_of"] == datetime(2026, 11, 1, 16, 0, tzinfo=UTC)  # 8:00 AM PST
    assert times["hour_before"] == datetime(2026, 11, 1, 17, 0, tzinfo=UTC)  # 9:00 AM PST


def test_day_before_stays_on_local_time_when_daylight_saving_starts():
    """US daylight saving starts Sun Mar 14, 2027. Appointment Mon Mar 15, 10:00 AM PDT."""
    starts_at = datetime(2027, 3, 15, 17, 0, tzinfo=UTC)
    # Sun Mar 14, 10:00 AM PDT = 17:00 UTC (the clocks already moved forward that night)
    assert reminder_times(starts_at, LA)["day_before"] == datetime(2027, 3, 14, 17, 0, tzinfo=UTC)
    starts_at = datetime(2027, 3, 14, 17, 0, tzinfo=UTC)  # Sun Mar 14, 10:00 AM PDT
    # Sat Mar 13, 10:00 AM PST = 18:00 UTC
    assert reminder_times(starts_at, LA)["day_before"] == datetime(2027, 3, 13, 18, 0, tzinfo=UTC)


def test_reminder_times_follow_the_users_time_zone():
    starts_at = datetime(2026, 10, 20, 14, 30, tzinfo=UTC)  # 10:30 AM in New York
    times = reminder_times(starts_at, "America/New_York")
    assert times["morning_of"] == datetime(2026, 10, 20, 12, 0, tzinfo=UTC)  # 8:00 AM EDT


def test_no_morning_of_reminder_for_an_early_appointment():
    starts_at = datetime(2026, 10, 20, 15, 30, tzinfo=UTC)  # 8:30 AM PDT
    assert set(reminder_times(starts_at, LA)) == {"day_before", "hour_before"}


# --- Created on booking, cancelled with the appointment ---------------------------------


def test_booking_creates_three_reminders(db, make_user, chen):
    appointment = _book(db, make_user(), chen)

    reminders = _reminders(db, appointment.id)
    assert set(reminders) == {"day_before", "morning_of", "hour_before"}
    expected = reminder_times(appointment.starts_at, LA)
    assert {kind: r.due_at for kind, r in reminders.items()} == expected
    assert {r.status for r in reminders.values()} == {"scheduled"}


def test_running_the_subscriber_twice_creates_no_duplicates(db, make_user, chen):
    appointment = _book(db, make_user(), chen)
    before = len(_reminders(db, appointment.id))

    on_appointment_booked(db, AppointmentBooked(appointment.id, appointment.user_id))
    db.commit()

    assert len(_reminders(db, appointment.id)) == before


def test_reminders_already_in_the_past_are_skipped(db, make_user, chen, monkeypatch):
    appointment = _book(db, make_user(), chen)
    db.execute(AppointmentReminder.__table__.delete())
    # Pretend the booking happened 30 minutes before the appointment.
    monkeypatch.setattr(
        "app.model.subscribers.reminder_scheduler._utcnow",
        lambda: appointment.starts_at - timedelta(minutes=30),
    )

    on_appointment_booked(db, AppointmentBooked(appointment.id, appointment.user_id))
    db.commit()

    assert _reminders(db, appointment.id) == {}


def test_cancelled_appointment_gets_no_reminders(db, make_user, chen):
    appointment = _book(db, make_user(), chen)
    day_before = _reminders(db, appointment.id)["day_before"]
    day_before.status = "sent"  # one was already sent before the cancellation
    appointment.status = "cancelled"
    events.publish(db, AppointmentCancelled(appointment.id, appointment.user_id))
    db.commit()

    reminders = _reminders(db, appointment.id)
    assert reminders["day_before"].status == "sent"  # history is kept
    assert reminders["morning_of"].status == "cancelled"
    assert reminders["hour_before"].status == "cancelled"
    assert run_once(now=appointment.starts_at - timedelta(minutes=1)) == {"appointment_reminder": 0}


# --- End to end: book, worker fires, banner shows it ------------------------------------


def test_booked_appointment_reminder_reaches_the_screen(client, db, make_user, chen, monkeypatch):
    margaret = make_user()
    appointment = _book(db, margaret, chen)
    day_before = reminder_times(appointment.starts_at, LA)["day_before"]

    assert run_once(now=day_before - timedelta(seconds=1)) == {"appointment_reminder": 0}
    assert run_once(now=day_before) == {"appointment_reminder": 1}

    monkeypatch.setattr("app.model.services.notifications._utcnow", lambda: day_before)
    client.login_as(margaret)
    feed = client.get("/api/v1/notifications").json()

    assert [item["timing"] for item in feed] == ["day_before"]
    assert feed[0]["status"] == "sent"
    assert feed[0]["message"].startswith("Reminder: you see Dr. Lisa Chen tomorrow at ")
    ok = client.post(f"/api/v1/appointment-reminders/{feed[0]['id']}/acknowledge")
    assert ok.json()["status"] == "acknowledged"
