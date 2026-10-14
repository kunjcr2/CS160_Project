"""PB-01: book an appointment in a slot found by AppointmentService.find_slots().

Payload: {"slot_id": "..."}. Proposed by the conversation controller (or POST /actions),
executed only by POST /actions/{id}/confirm.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.healthcare import (
    ProviderUnavailable,
    Slot,
    SlotUnavailable,
    get_healthcare_provider,
    parse_slot_id,
)
from app.model.entities import Appointment, Provider, User
from app.model.events import AppointmentBooked, events
from app.model.repositories import appointments as repo
from app.model.services.appointment_service import AppointmentService
from app.views import messages
from app.views.formatting import spoken_date, spoken_date_time, spoken_list, spoken_time

from .base import ActionCommand, ActionNotPossible
from .registry import register


def _slot_unknown() -> ActionNotPossible:
    return ActionNotPossible("slot_not_found", messages.BOOKING_SLOT_UNKNOWN)


def _provider_unavailable(provider: Provider) -> ActionNotPossible:
    message = (
        messages.BOOKING_FAILED.format(phone=provider.phone)
        if provider.phone
        else messages.BOOKING_FAILED_NO_PHONE
    )
    return ActionNotPossible("provider_unavailable", message)


@register
class BookAppointment(ActionCommand):
    action_type = "book_appointment"
    reversible = False  # undo is cancel (Sprint 3), a separate confirmed action

    def __init__(self, user: User, payload: dict) -> None:
        super().__init__(user, payload)
        self.slot_id = str(payload.get("slot_id", ""))
        try:
            self.practitioner_ref, self.start = parse_slot_id(self.slot_id)
        except ValueError:
            self.practitioner_ref, self.start = None, None
        self.api = get_healthcare_provider()

    def summary(self, session: Session) -> str:
        provider = self._provider(session)
        tz = self.user.timezone
        return messages.BOOKING_CONFIRM.format(
            doctor=provider.name,
            specialty=provider.specialty,
            date=spoken_date(self.start, tz),
            time=spoken_time(self.start, tz),
            location=provider.location,
        )

    def revalidate(self, session: Session) -> None:
        self._free_slot(session, self._provider(session))

    def execute(self, session: Session) -> dict:
        provider = self._provider(session)
        slot = self._free_slot(session, provider)

        # Claim the slot in our database first: the partial unique index on
        # (provider_id, starts_at) makes a second booking of the same slot fail here.
        appointment = Appointment(
            user_id=self.user.id,
            provider_id=provider.id,
            starts_at=slot.start,
            ends_at=slot.end,
            location=provider.location,
            status="booked",
        )
        session.add(appointment)
        try:
            session.flush()
        except IntegrityError:
            raise ActionNotPossible("slot_taken", messages.BOOKING_SLOT_TAKEN_NO_OPTIONS) from None

        try:
            appointment.external_ref = self.api.book(slot.id, patient_ref=str(self.user.id))
        except SlotUnavailable:
            raise self._slot_taken(session, provider) from None
        except ProviderUnavailable:
            raise _provider_unavailable(provider) from None

        try:
            session.flush()
            events.publish(session, AppointmentBooked(appointment.id, self.user.id))
        except Exception:
            self.api.cancel(appointment.external_ref)  # don't leave a booking we don't record
            raise
        return {
            "appointment_id": str(appointment.id),
            "provider_name": provider.name,
            "starts_at": slot.start.isoformat(),
        }

    def success_message(self, result: dict) -> str:
        starts_at = datetime.fromisoformat(result["starts_at"])
        return messages.BOOKING_DONE.format(
            doctor=result["provider_name"],
            date=spoken_date(starts_at, self.user.timezone),
            time=spoken_time(starts_at, self.user.timezone),
        )

    def _provider(self, session: Session) -> Provider:
        provider = repo.provider_by_ref(session, self.practitioner_ref or "")
        if provider is None:
            raise _slot_unknown()
        return provider

    def _free_slot(self, session: Session, provider: Provider) -> Slot:
        if self.start <= datetime.now(UTC):
            raise _slot_unknown()
        window_end = self.start + timedelta(minutes=1)
        try:
            found = self.api.search_slots(provider.external_ref, self.start, window_end)
        except ProviderUnavailable:
            raise _provider_unavailable(provider) from None
        free = [slot for slot in found if slot.id == self.slot_id]
        if not free or repo.booked_starts(session, provider.id, self.start, window_end):
            raise self._slot_taken(session, provider)
        return free[0]

    def _slot_taken(self, session: Session, provider: Provider) -> ActionNotPossible:
        """Explain, and offer the next free times with the same doctor this week."""
        day = self.start.astimezone(ZoneInfo(self.user.timezone)).date()
        try:
            options = AppointmentService(session).find_slots(
                self.user, provider, day, day + timedelta(days=7)
            )
        except ProviderUnavailable:
            options = []
        if not options:
            return ActionNotPossible("slot_taken", messages.BOOKING_SLOT_TAKEN_NO_OPTIONS)
        times = spoken_list([spoken_date_time(o.starts_at, self.user.timezone) for o in options])
        return ActionNotPossible("slot_taken", messages.BOOKING_SLOT_TAKEN.format(options=times))
