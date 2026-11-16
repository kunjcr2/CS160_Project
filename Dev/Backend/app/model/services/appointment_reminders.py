"""PB-02 appointment reminders as a ReminderSource, plus the OK button (acknowledge)."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model.entities import Appointment, AppointmentReminder, Provider, User
from app.views import messages
from app.views.formatting import spoken_time

from .reminder_source import Notification

BATCH_SIZE = 100  # reminders claimed per worker pass


class ReminderNotFound(Exception):  # noqa: N818
    """No such reminder, or it belongs to someone else (404)."""


class ReminderAlreadyAnswered(Exception):  # noqa: N818
    """Not waiting for an answer: not sent yet, or already acknowledged (409)."""


class AppointmentReminderSource:
    kind = "appointment_reminder"

    def send_due(self, session: Session, now: datetime) -> int:
        due = session.scalars(
            select(AppointmentReminder)
            .where(AppointmentReminder.status == "scheduled", AppointmentReminder.due_at <= now)
            .order_by(AppointmentReminder.due_at)
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        ).all()
        sent = 0
        for reminder in due:
            appointment = session.get(Appointment, reminder.appointment_id)
            if appointment.status != "booked" or appointment.starts_at <= now:
                reminder.status = "cancelled"  # too late, or the appointment is off
                continue
            reminder.status = "sent"
            reminder.sent_at = now
            reminder.attempts += 1
            sent += 1
        session.flush()
        return sent

    def follow_up(self, session: Session, now: datetime) -> int:
        return 0  # appointment reminders only need an OK; nothing to chase

    def recent_for_user(
        self, session: Session, user: User, since: datetime, now: datetime
    ) -> list[Notification]:
        rows = session.execute(
            select(AppointmentReminder, Appointment, Provider)
            .join(Appointment, AppointmentReminder.appointment_id == Appointment.id)
            .join(Provider, Appointment.provider_id == Provider.id)
            .where(
                AppointmentReminder.user_id == user.id,
                AppointmentReminder.status.in_(("sent", "acknowledged")),
                AppointmentReminder.due_at >= since,
                AppointmentReminder.due_at <= now,
            )
            .order_by(AppointmentReminder.due_at)
        ).all()
        return [to_notification(r, a, p, user) for r, a, p in rows]

    def acknowledge(self, session: Session, user: User, reminder_id: uuid.UUID) -> Notification:
        """The user tapped OK."""
        reminder = session.scalar(
            select(AppointmentReminder)
            .where(AppointmentReminder.id == reminder_id, AppointmentReminder.user_id == user.id)
            .with_for_update()
        )
        if reminder is None:
            raise ReminderNotFound(reminder_id)
        if reminder.status != "sent":
            raise ReminderAlreadyAnswered(reminder.status)
        reminder.status = "acknowledged"
        session.flush()
        appointment = session.get(Appointment, reminder.appointment_id)
        provider = session.get(Provider, appointment.provider_id)
        return to_notification(reminder, appointment, provider, user)


def to_notification(
    reminder: AppointmentReminder, appointment: Appointment, provider: Provider, user: User
) -> Notification:
    message = messages.REMINDERS[reminder.kind].format(
        doctor=provider.name,
        time=spoken_time(appointment.starts_at, user.timezone),
        location=appointment.location,
    )
    return Notification(
        kind=AppointmentReminderSource.kind,
        id=str(reminder.id),
        due_at=reminder.due_at,
        status=reminder.status,
        message=message,
        fields={
            "timing": reminder.kind,  # day_before, morning_of, hour_before
            "appointment_id": str(appointment.id),
            "provider_name": provider.name,
            "starts_at": appointment.starts_at,
            "location": appointment.location,
        },
    )
