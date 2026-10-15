"""PB-03: what happens to a medication dose after it is created.

Worker side (Amar's reminder worker will call these about every 30 s):
- send_due():  due doses -> "sent" (shown to the user).
- follow_up(): no answer after 30 min -> shown once more; after 60 min -> "missed".

User side:
- mark_taken(), mark_missed(). Only the person who takes the medicine can answer.

Status flow:  scheduled -> sent -> taken | missed,  or cancelled / failed.
Nothing here commits; the caller does.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.model.entities import MedicationReminder, User

BATCH_SIZE = 100  # at most this many doses per worker run
EARLY_WINDOW = timedelta(hours=1)  # a dose can be answered up to 1 hour before it's due


class ReminderNotFoundError(Exception):
    """No such dose, or it belongs to someone else (the endpoint answers 404)."""


class ReminderNotChangeableError(Exception):
    """The dose can't be changed now. `code` says why: the current status, or "too_early"."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# ---------- Worker side ----------


class MedicationReminderSource:
    """Medication doses for the reminder worker (same shape as Amar's ReminderSource)."""

    kind = "medication_reminder"

    def send_due(self, db: DbSession, now: datetime) -> int:
        """Show every dose that is due. Returns how many were sent."""
        due = db.scalars(
            select(MedicationReminder)
            .where(MedicationReminder.status == "scheduled", MedicationReminder.due_at <= now)
            .order_by(MedicationReminder.due_at)
            .limit(BATCH_SIZE)
            # SKIP LOCKED: if two workers run at once, each takes different rows.
            .with_for_update(skip_locked=True)
        ).all()
        too_old = now - timedelta(minutes=settings.medication_missed_minutes)
        sent = 0
        for dose in due:
            if dose.schedule.medication.stopped_at is not None:
                dose.status = "cancelled"  # the medicine was stopped
            elif dose.due_at < too_old:
                dose.status = "failed"  # the worker was down; we never reminded them
            else:
                dose.status = "sent"
                dose.sent_at = now
                dose.attempts = 1
                sent += 1
        db.flush()
        return sent

    def follow_up(self, db: DbSession, now: datetime) -> int:
        """Chase unanswered doses: show once more after 30 min, "missed" after 60 min."""
        reprompt_before = now - timedelta(minutes=settings.medication_reprompt_minutes)
        missed_before = now - timedelta(minutes=settings.medication_missed_minutes)
        waiting = db.scalars(
            select(MedicationReminder)
            .where(
                MedicationReminder.status == "sent", MedicationReminder.sent_at <= reprompt_before
            )
            .order_by(MedicationReminder.sent_at)
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        ).all()
        changed = 0
        for dose in waiting:
            if dose.sent_at <= missed_before:
                dose.status = "missed"
                dose.confirmed_at = now
                changed += 1
            elif dose.attempts < 2:
                dose.attempts = 2  # the screen shows it again
                changed += 1
        db.flush()
        return changed


# ---------- User side ----------


def _lock_own_dose(db: DbSession, reminder_id: uuid.UUID, user: User) -> MedicationReminder:
    """The user's own dose, locked so a double tap is handled one at a time."""
    dose = db.scalar(
        select(MedicationReminder)
        .where(MedicationReminder.id == reminder_id, MedicationReminder.user_id == user.id)
        .with_for_update()
    )
    if dose is None:
        raise ReminderNotFoundError()
    return dose


def _check_not_too_early(dose: MedicationReminder, now: datetime) -> None:
    if dose.due_at > now + EARLY_WINDOW:
        raise ReminderNotChangeableError("too_early")


def mark_taken(
    db: DbSession, reminder_id: uuid.UUID, user: User, now: datetime
) -> MedicationReminder:
    """The user took the dose. A "missed" dose can be corrected to "taken".

    Saying "taken" twice is fine: the second time changes nothing.
    """
    dose = _lock_own_dose(db, reminder_id, user)
    if dose.status == "taken":
        return dose
    if dose.status not in ("scheduled", "sent", "missed"):
        raise ReminderNotChangeableError(dose.status)
    _check_not_too_early(dose, now)
    dose.status = "taken"
    dose.confirmed_at = now
    db.flush()
    return dose


def mark_missed(
    db: DbSession, reminder_id: uuid.UUID, user: User, now: datetime
) -> MedicationReminder:
    """The user says they skipped the dose. Saying it twice changes nothing."""
    dose = _lock_own_dose(db, reminder_id, user)
    if dose.status == "missed":
        return dose
    if dose.status not in ("scheduled", "sent"):
        raise ReminderNotChangeableError(dose.status)
    _check_not_too_early(dose, now)
    dose.status = "missed"
    dose.confirmed_at = now
    db.flush()
    return dose
