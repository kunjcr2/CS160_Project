"""HealthcareProvider: the list of things any "doctor's office" system must do.

The model (services and commands) talks ONLY to this interface, never to a real or
mock system directly. Today the only implementation is MockHealthcareProvider (mock.py).
Later, a real FHIR client can be added without changing the model.

The data shapes follow FHIR resources: Practitioner, Slot, Appointment.
All datetimes are timezone-aware and in UTC.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime

# ---------- Errors ----------
# Each error means something different for the user, so callers can
# catch them one by one and give the right message.


class HealthcareError(Exception):
    """Base class for every error from a healthcare provider."""


class ProviderUnavailableError(HealthcareError):
    """The office system is down or too slow. Safe to try again later."""


class SlotUnavailableError(HealthcareError):
    """The slot is already taken or does not exist. Offer other times."""


class BookingNotFoundError(HealthcareError):
    """No booking with this reference exists in the office system."""


# ---------- Data shapes ----------
# frozen=True: once created, the values can't be changed by mistake.


@dataclass(frozen=True)
class Practitioner:
    """A doctor or clinician (FHIR Practitioner)."""

    external_ref: str  # this doctor's id inside the office system
    name: str
    specialty: str
    location: str
    phone: str | None = None


@dataclass(frozen=True)
class Slot:
    """A free time with one practitioner (FHIR Slot). Never stored in our database."""

    id: str  # see make_slot_id(); pass it back to book "option 2"
    practitioner_ref: str
    starts_at: datetime  # UTC
    ends_at: datetime  # UTC


@dataclass(frozen=True)
class Booking:
    """A confirmed appointment inside the office system (FHIR Appointment)."""

    external_ref: str  # booking id in the office system; saved in appointments.external_ref
    practitioner_ref: str
    starts_at: datetime  # UTC
    ends_at: datetime  # UTC
    location: str


# ---------- Slot ids ----------
# A slot id is "<practitioner_ref>|<start in UTC as YYYYMMDDTHHMMZ>", for example
# "mock-prac-cardiology-1|20261019T1600Z". The AI or the screen can pass it back to book
# that slot:  office.book(*parse_slot_id(slot_id), patient_ref)
# Same format as Amar's booking code, so his payloads keep working.


def make_slot_id(practitioner_ref: str, starts_at: datetime) -> str:
    """Build the id of the slot that starts at starts_at with this practitioner."""
    return f"{practitioner_ref}|{starts_at.astimezone(UTC):%Y%m%dT%H%MZ}"


def parse_slot_id(slot_id: str) -> tuple[str, datetime]:
    """Split a slot id into (practitioner_ref, starts_at in UTC).

    Raises ValueError if the text is not a slot id.
    """
    practitioner_ref, _, stamp = slot_id.rpartition("|")
    if not practitioner_ref:
        raise ValueError(f"Not a slot id: {slot_id!r}")
    return practitioner_ref, datetime.strptime(stamp, "%Y%m%dT%H%MZ").replace(tzinfo=UTC)


# ---------- The interface ----------


class HealthcareProvider(ABC):
    """What every doctor's office system must be able to do.

    Every method can raise ProviderUnavailableError.
    """

    @abstractmethod
    def list_practitioners(self) -> list[Practitioner]:
        """Return all doctors in the office system."""

    @abstractmethod
    def find_slots(self, practitioner_ref: str, start: datetime, end: datetime) -> list[Slot]:
        """Return FREE slots for one doctor between start and end (UTC), sorted by time."""

    @abstractmethod
    def book(self, practitioner_ref: str, starts_at: datetime, patient_ref: str) -> Booking:
        """Book the slot that starts at starts_at.

        patient_ref is our user's id as text. Raises SlotUnavailableError if the slot
        is taken or does not exist.
        """

    @abstractmethod
    def cancel(self, booking_ref: str) -> None:
        """Cancel a booking. Raises BookingNotFoundError if it does not exist."""
