"""PB-01: cancel one of the user's booked, future appointments.

Payload: {"appointment_id": "..."}. Like booking, it is the user's own appointment
(appointments are looked up by owner, plan §5.2). Reminders stop through the
AppointmentCancelled event (PB-02); this command never touches reminder rows.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.adapters.healthcare.interface import ProviderUnavailableError
from app.model.entities import Appointment, Provider, User
from app.model.events import AppointmentCancelled, events
from app.model.repositories import appointments as repo
from app.views import messages
from app.views.formatting import spoken_date, spoken_time

from .base import ActionCommand, ActionNotPossible
from .registry import register


def appointment_id_from(payload: dict) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(payload.get("appointment_id", "")))
    except ValueError:
        return None


def changeable_appointment(
    session: Session, user: User, appointment_id: uuid.UUID | None, *, lock: bool = False
) -> Appointment:
    """The user's own appointment, if it is still booked and hasn't started.

    Someone else's appointment looks exactly like a missing one (plan §5.2).
    """
    if appointment_id is None:
        raise ActionNotPossible("appointment_not_found", messages.APPOINTMENT_UNKNOWN)
    find = repo.lock_owned if lock else repo.get_owned
    appointment = find(session, appointment_id, user.id)
    if appointment is None:
        raise ActionNotPossible("appointment_not_found", messages.APPOINTMENT_UNKNOWN)
    if not appointment.can_cancel(datetime.now(UTC)):
        raise ActionNotPossible("not_changeable", messages.APPOINTMENT_NOT_CHANGEABLE)
    return appointment


def office_failed(provider: Provider, with_phone: str, without_phone: str) -> ActionNotPossible:
    message = with_phone.format(phone=provider.phone) if provider.phone else without_phone
    return ActionNotPossible("provider_unavailable", message)


@register
class CancelAppointment(ActionCommand):
    action_type = "cancel_appointment"
    reversible = False  # the slot may be given to someone else right away

    def __init__(self, user: User, payload: dict, **adapters) -> None:
        super().__init__(user, payload, **adapters)
        self.appointment_id = appointment_id_from(payload)

    def summary(self, session: Session) -> str:
        appointment = changeable_appointment(session, self.user, self.appointment_id)
        return self._say(messages.CANCEL_CONFIRM, session, appointment)

    def revalidate(self, session: Session) -> None:
        changeable_appointment(session, self.user, self.appointment_id)

    def execute(self, session: Session) -> dict:
        appointment = changeable_appointment(session, self.user, self.appointment_id, lock=True)
        provider = session.get(Provider, appointment.provider_id)
        appointment.status = "cancelled"
        session.flush()
        events.publish(session, AppointmentCancelled(appointment.id, self.user.id))
        # The office goes last: if it fails, raising rolls back everything above.
        if appointment.external_ref:
            try:
                self.healthcare.cancel(appointment.external_ref)
            except ProviderUnavailableError:
                raise office_failed(
                    provider, messages.CANCEL_FAILED, messages.CANCEL_FAILED_NO_PHONE
                ) from None
        return {
            "appointment_id": str(appointment.id),
            "provider_name": provider.name,
            "starts_at": appointment.starts_at.isoformat(),
        }

    def success_message(self, result: dict) -> str:
        starts_at = datetime.fromisoformat(result["starts_at"])
        tz = self.user.timezone
        return messages.CANCEL_DONE.format(
            doctor=result["provider_name"],
            date=spoken_date(starts_at, tz),
            time=spoken_time(starts_at, tz),
        )

    def _say(self, template: str, session: Session, appointment: Appointment) -> str:
        provider = session.get(Provider, appointment.provider_id)
        tz = self.user.timezone
        return template.format(
            doctor=provider.name,
            date=spoken_date(appointment.starts_at, tz),
            time=spoken_time(appointment.starts_at, tz),
        )
