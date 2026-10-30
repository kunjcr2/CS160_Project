"""Reminder worker and notifications (S2-10): due reminders are sent once; the screen
learns about them by polling GET /notifications."""

from datetime import UTC, datetime, timedelta

import pytest

from app.db import SessionLocal
from app.model.entities import Appointment, AppointmentReminder, Provider, User
from app.workers.reminders import run_once

NOW = datetime(2026, 10, 19, 17, 30, tzinfo=UTC)  # Monday 10:30 AM in Los Angeles


@pytest.fixture
def appointment(db, make_user):
    """Margaret sees Dr. Chen on Tuesday Oct 20 at 10:30 AM Los Angeles time."""
    user = make_user("Margaret")
    provider = Provider(
        name="Dr. Lisa Chen", specialty="Cardiology", location="Valley Medical", external_ref="c"
    )
    db.add(provider)
    db.flush()
    appointment = Appointment(
        user_id=user.id,
        provider_id=provider.id,
        starts_at=datetime(2026, 10, 20, 17, 30, tzinfo=UTC),
        ends_at=datetime(2026, 10, 20, 18, 0, tzinfo=UTC),
        location="Valley Medical",
        status="booked",
    )
    db.add(appointment)
    db.commit()
    return appointment


def add_reminder(db, appointment, kind="day_before", due_at=NOW, status="scheduled"):
    reminder = AppointmentReminder(
        appointment_id=appointment.id,
        user_id=appointment.user_id,
        kind=kind,
        due_at=due_at,
        status=status,
    )
    db.add(reminder)
    db.commit()
    return reminder


def test_due_reminders_are_sent_once(db, appointment):
    due = add_reminder(db, appointment, "day_before", due_at=NOW - timedelta(minutes=1))
    later = add_reminder(db, appointment, "hour_before", due_at=NOW + timedelta(hours=23))

    assert run_once(now=NOW) == {"appointment_reminder": 1}
    assert run_once(now=NOW) == {"appointment_reminder": 0}  # second pass: nothing new

    db.refresh(due)
    db.refresh(later)
    assert (due.status, due.sent_at, due.attempts) == ("sent", NOW, 1)
    assert later.status == "scheduled"


def test_cancelled_and_too_late_reminders_are_not_sent(db, appointment):
    cancelled = add_reminder(db, appointment, "day_before", status="cancelled")
    # Worker was down: the appointment already started when the reminder gets picked up.
    too_late = add_reminder(db, appointment, "hour_before", due_at=NOW)

    run_once(now=appointment.starts_at + timedelta(minutes=5))

    db.refresh(cancelled)
    db.refresh(too_late)
    assert cancelled.status == "cancelled"
    assert too_late.status == "cancelled"


def test_reminders_for_a_cancelled_appointment_are_not_sent(db, appointment):
    reminder = add_reminder(db, appointment)
    appointment.status = "cancelled"
    db.commit()

    run_once(now=NOW)

    db.refresh(reminder)
    assert reminder.status == "cancelled"


def test_notification_feed_shows_sent_reminders_with_their_message(
    client, db, appointment, monkeypatch
):
    sent = add_reminder(db, appointment, "day_before", due_at=NOW - timedelta(minutes=5))
    add_reminder(db, appointment, "morning_of", due_at=NOW + timedelta(hours=22))  # not yet due
    run_once(now=NOW)
    monkeypatch.setattr("app.model.services.notifications._utcnow", lambda: NOW)

    client.login_as(_user(db, appointment))
    feed = client.get("/api/v1/notifications").json()

    assert len(feed) == 1
    item = feed[0]
    assert item["id"] == str(sent.id)
    assert item["kind"] == "appointment_reminder"
    assert item["status"] == "sent"
    assert item["timing"] == "day_before"
    assert item["provider_name"] == "Dr. Lisa Chen"
    assert item["appointment_id"] == str(appointment.id)
    assert item["message"] == (
        "Reminder: you see Dr. Lisa Chen tomorrow at 10:30 AM, at Valley Medical."
    )


def test_feed_only_shows_the_last_12_hours_and_only_your_own(
    client, db, appointment, make_user, monkeypatch
):
    add_reminder(db, appointment, "day_before", due_at=NOW - timedelta(hours=13), status="sent")
    monkeypatch.setattr("app.model.services.notifications._utcnow", lambda: NOW)

    client.login_as(_user(db, appointment))
    assert client.get("/api/v1/notifications").json() == []

    add_reminder(db, appointment, "morning_of", due_at=NOW - timedelta(hours=1), status="sent")
    assert len(client.get("/api/v1/notifications").json()) == 1
    client.login_as(make_user("David"))
    assert client.get("/api/v1/notifications").json() == []


def test_ok_button_acknowledges_once(client, db, appointment, make_user):
    sent = add_reminder(db, appointment, "day_before", status="sent")
    not_yet = add_reminder(db, appointment, "hour_before", due_at=NOW + timedelta(days=1))

    client.login_as(make_user("David"))
    assert client.post(f"/api/v1/appointment-reminders/{sent.id}/acknowledge").status_code == 404

    client.login_as(_user(db, appointment))
    first = client.post(f"/api/v1/appointment-reminders/{sent.id}/acknowledge")
    again = client.post(f"/api/v1/appointment-reminders/{sent.id}/acknowledge")
    early = client.post(f"/api/v1/appointment-reminders/{not_yet.id}/acknowledge")

    assert first.status_code == 200
    assert first.json()["status"] == "acknowledged"
    assert again.status_code == 409
    assert early.status_code == 409


def test_a_failing_source_does_not_stop_the_worker(monkeypatch):
    class Broken:
        kind = "broken"

        def send_due(self, session, now):
            raise RuntimeError("boom")

    class Working:
        kind = "working"

        def send_due(self, session, now):
            return 2

        def follow_up(self, session, now):
            return 0

    monkeypatch.setattr("app.workers.reminders.SOURCES", [Broken(), Working()])
    assert run_once(SessionLocal, NOW) == {"broken": 0, "working": 2}


def _user(db, appointment) -> User:
    return db.get(User, appointment.user_id)
