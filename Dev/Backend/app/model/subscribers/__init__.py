"""Observers of domain events: reminder scheduler, notifier, audit logger."""

from app.model.events import AppointmentBooked, AppointmentCancelled, EventPublisher, events

from . import reminder_scheduler


def register_all(publisher: EventPublisher = events) -> None:
    """Connect every subscriber to its events. Called once by the composition root
    (app/main.py); calling it again is harmless."""
    publisher.subscribe(AppointmentBooked, reminder_scheduler.on_appointment_booked)
    publisher.subscribe(AppointmentCancelled, reminder_scheduler.on_appointment_cancelled)
