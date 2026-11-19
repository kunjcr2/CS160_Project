"""PB-01: move one of the user's booked appointments to another free slot with the SAME
doctor (another doctor is a cancel plus a new booking).

Payload: {"appointment_id": "...", "slot_id": "..."}; slot_id comes from GET /slots,
exactly as for booking. Reuses BookAppointment's slot checks. The old appointment is
marked cancelled and a new one is booked, so the old row stays as history; reminders
move through the AppointmentRescheduled event (PB-02).
"""

import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.healthcare.interface import ProviderUnavailableError, SlotUnavailableError
from app.model.entities import Appointment, Provider, User
from app.model.events import AppointmentRescheduled, events
from app.views import messages
from app.views.formatting import spoken_date, spoken_date_time, spoken_time

from .base import ActionNotPossible
from .book_appointment import BookAppointment
from .cancel_appointment import appointment_id_from, changeable_appointment, office_failed
from .registry import register

log = logging.getLogger(__name__)


def _failed(provider: Provider) -> ActionNotPossible:
    return office_failed(provider, messages.RESCHEDULE_FAILED, messages.RESCHEDULE_FAILED_NO_PHONE)


@register
class RescheduleAppointment(BookAppointment):
    action_type = "reschedule_appointment"
    reversible = False

    def __init__(self, user: User, payload: dict, **adapters) -> None:
        super().__init__(user, payload, **adapters)  # parses slot_id
        self.appointment_id = appointment_id_from(payload)

    def summary(self, session: Session) -> str:
        old = changeable_appointment(session, self.user, self.appointment_id)
        provider = self._same_doctor(session, old)
        tz = self.user.timezone
        return messages.RESCHEDULE_CONFIRM.format(
            doctor=provider.name,
            old=spoken_date_time(old.starts_at, tz),
            new=spoken_date_time(self.start, tz),
            location=provider.location,
        )

    def revalidate(self, session: Session) -> None:
        old = changeable_appointment(session, self.user, self.appointment_id)
        self._free_slot(session, self._same_doctor(session, old))

    def execute(self, session: Session) -> dict:
        old = changeable_appointment(session, self.user, self.appointment_id, lock=True)
        provider = self._same_doctor(session, old)
        slot = self._free_slot(session, provider)

        # 1. Claim the new time in our database (the unique index stops a double booking).
        new = Appointment(
            user_id=self.user.id,
            provider_id=provider.id,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
            location=provider.location,
            status="booked",
        )
        session.add(new)
        try:
            session.flush()
        except IntegrityError:
            raise ActionNotPossible("slot_taken", messages.BOOKING_SLOT_TAKEN_NO_OPTIONS) from None

        # 2. Book it at the office.
        try:
            booking = self.healthcare.book(
                provider.external_ref, slot.starts_at, patient_ref=str(self.user.id)
            )
        except SlotUnavailableError:
            raise self._slot_taken(session, provider) from None
        except ProviderUnavailableError:
            raise _failed(provider) from None
        new.external_ref = booking.external_ref

        # 3. Retire the old one, here and then at the office. If anything fails, give the
        #    new office booking back; raising rolls back our database changes.
        try:
            old.status = "cancelled"
            session.flush()
            events.publish(session, AppointmentRescheduled(old.id, new.id, self.user.id))
            if old.external_ref:
                self.healthcare.cancel(old.external_ref)
        except Exception as error:
            self._give_back(new.external_ref)
            if isinstance(error, ProviderUnavailableError):
                raise _failed(provider) from None
            raise
        return {
            "appointment_id": str(new.id),
            "previous_appointment_id": str(old.id),
            "provider_name": provider.name,
            "starts_at": slot.starts_at.isoformat(),
        }

    def success_message(self, result: dict) -> str:
        starts_at = datetime.fromisoformat(result["starts_at"])
        tz = self.user.timezone
        return messages.RESCHEDULE_DONE.format(
            doctor=result["provider_name"],
            date=spoken_date(starts_at, tz),
            time=spoken_time(starts_at, tz),
        )

    def _same_doctor(self, session: Session, old: Appointment) -> Provider:
        provider = self._provider(session)  # raises if the slot id isn't a real slot
        if provider.id != old.provider_id:
            raise ActionNotPossible("different_doctor", messages.RESCHEDULE_OTHER_DOCTOR)
        return provider

    def _give_back(self, booking_ref: str) -> None:
        try:
            self.healthcare.cancel(booking_ref)
        except ProviderUnavailableError:
            # Our database is the source of truth (plan §6.2): the new appointment row is
            # rolled back, so this office booking is simply never used.
            log.warning("Couldn't release office booking %s after a failed reschedule", booking_ref)
