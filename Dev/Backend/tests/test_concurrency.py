"""Trust-critical races (S2-12, plan §12): these run real parallel database sessions in
threads, the way two requests or two worker processes would."""

import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from conftest import next_tuesday
from sqlalchemy import func, select

from app.db import SessionLocal
from app.model.commands.book_appointment import BookAppointment
from app.model.entities import Appointment, AppointmentReminder, Provider, User
from app.model.services.action_service import ActionService
from app.model.services.appointment_reminders import AppointmentReminderSource
from app.model.services.appointment_service import AppointmentService
from app.workers.reminders import run_once


@pytest.fixture(autouse=True)
def _fresh_provider(mock_provider):
    """Every test gets its own mock provider (see conftest)."""


def in_parallel(*jobs):
    """Run each job in its own thread, released at the same moment; return their results."""
    start = threading.Barrier(len(jobs))
    results, errors = [None] * len(jobs), []

    def run(index, job):
        start.wait()
        try:
            results[index] = job()
        except Exception as error:  # surfaced below, not swallowed
            errors.append(error)

    threads = [threading.Thread(target=run, args=(i, job)) for i, job in enumerate(jobs)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not errors, errors
    return results


@pytest.fixture
def slow_revalidate(monkeypatch):
    """Call after proposing: each confirm then pauses right after reading the action,
    so two confirms really are in progress at the same time."""

    def enable():
        original = BookAppointment.revalidate

        def slow(self, session):
            time.sleep(0.3)
            original(self, session)

        monkeypatch.setattr(BookAppointment, "revalidate", slow)

    return enable


def confirm_in_new_session(action_id, user_id):
    with SessionLocal() as session:
        outcome = ActionService(session).confirm(action_id, session.get(User, user_id))
        session.commit()
        return outcome.action.status, outcome.message


def _count(db, model, *where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where))


def test_two_simultaneous_confirms_book_once(db, make_user, chen, slow_revalidate):
    margaret = make_user()
    slot = AppointmentService(db).find_slots(margaret, chen, next_tuesday(), next_tuesday())[0]
    action = ActionService(db).propose(margaret, "book_appointment", {"slot_id": slot.slot_id})
    db.commit()
    slow_revalidate()

    first, second = in_parallel(
        lambda: confirm_in_new_session(action.id, margaret.id),
        lambda: confirm_in_new_session(action.id, margaret.id),
    )

    assert first == second  # the second request gets the first one's answer
    assert first[0] == "executed"
    assert _count(db, Appointment) == 1


def test_two_people_confirming_the_same_slot_get_one_booking(db, make_user, chen, slow_revalidate):
    margaret, david = make_user("Margaret"), make_user("David")
    slot = AppointmentService(db).find_slots(margaret, chen, next_tuesday(), next_tuesday())[0]
    actions = ActionService(db)
    hers = actions.propose(margaret, "book_appointment", {"slot_id": slot.slot_id})
    his = actions.propose(david, "book_appointment", {"slot_id": slot.slot_id})
    db.commit()
    slow_revalidate()  # both pass the "is the slot free?" check before either books

    results = in_parallel(
        lambda: confirm_in_new_session(hers.id, margaret.id),
        lambda: confirm_in_new_session(his.id, david.id),
    )

    assert sorted(status for status, _ in results) == ["executed", "failed"]
    failed_message = next(message for status, message in results if status == "failed")
    assert failed_message.startswith("Sorry, that time was just taken.")
    assert _count(db, Appointment, Appointment.provider_id == chen.id) == 1


class SlowAppointmentReminderSource(AppointmentReminderSource):
    """Holds its claimed rows a moment longer, so two workers truly overlap."""

    def send_due(self, session, now):
        sent = super().send_due(session, now)
        time.sleep(0.3)
        return sent


def test_two_workers_send_each_reminder_exactly_once(db, make_user, monkeypatch):
    user = make_user()
    provider = Provider(
        name="Dr. Lisa Chen", specialty="Cardiology", location="A", external_ref="c"
    )
    db.add(provider)
    db.flush()
    now = datetime(2026, 10, 19, 17, 30, tzinfo=UTC)
    for day in range(30):
        starts_at = now + timedelta(days=day + 1)
        appointment = Appointment(
            user_id=user.id,
            provider_id=provider.id,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=30),
            location="A",
            status="booked",
        )
        db.add(appointment)
        db.flush()
        db.add(
            AppointmentReminder(
                appointment_id=appointment.id,
                user_id=user.id,
                kind="day_before",
                due_at=now - timedelta(minutes=1),
            )
        )
    db.commit()
    monkeypatch.setattr("app.model.services.appointment_reminders.BATCH_SIZE", 10)
    monkeypatch.setattr("app.workers.reminders.SOURCES", [SlowAppointmentReminderSource()])

    first, second = in_parallel(lambda: run_once(now=now), lambda: run_once(now=now))

    # Each worker claimed its own batch of 10; SKIP LOCKED kept them apart.
    assert first == second == {"appointment_reminder": 10}
    sent = db.scalars(select(AppointmentReminder).where(AppointmentReminder.status == "sent"))
    assert [reminder.attempts for reminder in sent] == [1] * 20
