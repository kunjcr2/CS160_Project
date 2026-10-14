"""HealthcareProvider interface (Strategy, plan §4, §6.2). Shaped after FHIR: a Slot is a
bookable time for a Practitioner; book() turns a Slot into an Appointment."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class SlotUnavailable(Exception):  # noqa: N818
    """The slot doesn't exist or is no longer free."""


class ProviderUnavailable(Exception):  # noqa: N818
    """The provider's system is down or timed out. Nothing was booked."""


@dataclass(frozen=True)
class Slot:
    id: str  # opaque to callers; pass it back to book()
    practitioner_ref: str  # providers.external_ref
    start: datetime  # UTC
    end: datetime  # UTC


def make_slot_id(practitioner_ref: str, start: datetime) -> str:
    return f"{practitioner_ref}|{start.astimezone(UTC):%Y%m%dT%H%MZ}"


def parse_slot_id(slot_id: str) -> tuple[str, datetime]:
    """Raises ValueError for anything that isn't a slot id."""
    practitioner_ref, _, stamp = slot_id.rpartition("|")
    if not practitioner_ref:
        raise ValueError(slot_id)
    return practitioner_ref, datetime.strptime(stamp, "%Y%m%dT%H%MZ").replace(tzinfo=UTC)


class HealthcareProvider(Protocol):
    def search_slots(self, practitioner_ref: str, start: datetime, end: datetime) -> list[Slot]:
        """Free slots starting in [start, end), earliest first."""
        ...

    def book(self, slot_id: str, patient_ref: str) -> str:
        """Book the slot and return the provider's booking id. Raises SlotUnavailable or
        ProviderUnavailable."""
        ...

    def cancel(self, booking_ref: str) -> None: ...
