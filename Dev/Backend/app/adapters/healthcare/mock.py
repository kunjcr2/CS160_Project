"""MockHealthcareProvider: a fake doctor's office for development, tests, and the demo.

- The doctors are fixed (Margaret's story). The seed script copies them into
  the providers table, so the external_ref values match.
- Free slots are generated, not stored: Monday to Friday, 9:00-17:00 office time,
  30 minutes each, no slots during lunch (12:00-13:00).
- Bookings live in memory only and disappear when the server restarts. Our own
  appointments table is the real record (its unique index still blocks double-booking).
- Slow calls and random failures can be turned on to test error paths.

Mock/demo data only. No real people, no real patients.
Error texts here are for developers; user-facing sentences live in views/messages.py.
"""

import random
import threading
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, time, timedelta
from time import sleep
from zoneinfo import ZoneInfo

from .interface import (
    Booking,
    BookingNotFoundError,
    HealthcareProvider,
    Practitioner,
    ProviderUnavailableError,
    Slot,
    SlotUnavailableError,
)

# ---------- Office hours ----------
OFFICE_TZ = ZoneInfo("America/Los_Angeles")  # zoneinfo handles daylight saving for us
OPEN_AT = time(9, 0)
CLOSE_AT = time(17, 0)
LUNCH_HOUR = 12  # no slots from 12:00 to 13:00
SLOT_LENGTH = timedelta(minutes=30)

# ---------- Fake doctors ----------
# 555-01xx phone numbers are reserved for fiction, so they never reach a real person.
PRACTITIONERS: tuple[Practitioner, ...] = (
    Practitioner(
        external_ref="mock-prac-cardiology-1",
        name="Dr. Elena Ruiz",
        specialty="Cardiology",
        location="Valley Heart Clinic, 100 Example Ave, San Jose, CA",
        phone="408-555-0101",
    ),
    Practitioner(
        external_ref="mock-prac-physical-therapy-1",
        name="Sam Patel, PT",
        specialty="Physical Therapy",
        location="MoveWell Physical Therapy, 200 Example Ave, San Jose, CA",
        phone="408-555-0102",
    ),
    Practitioner(
        external_ref="mock-prac-primary-care-1",
        name="Dr. Grace Kim",
        specialty="Primary Care",
        location="Downtown Family Medicine, 300 Example Ave, San Jose, CA",
        phone="408-555-0103",
    ),
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _require_aware(*values: datetime) -> None:
    """Refuse datetimes without a time zone; they cause silent time bugs."""
    for value in values:
        if value.tzinfo is None:
            raise ValueError("Use timezone-aware datetimes (UTC).")


def _is_office_slot(starts_at: datetime) -> bool:
    """True if a slot can start at this moment (weekday, office hours, not lunch)."""
    local = starts_at.astimezone(OFFICE_TZ)
    return (
        local.weekday() < 5  # 0 = Monday ... 4 = Friday
        and local.minute in (0, 30)
        and local.second == 0
        and local.microsecond == 0
        and OPEN_AT <= local.time() < CLOSE_AT
        and local.hour != LUNCH_HOUR
    )


def _office_slots(practitioner_ref: str, start: datetime, end: datetime) -> Iterator[Slot]:
    """Every slot (free or not) between start and end, in time order."""
    day = start.astimezone(OFFICE_TZ).date()
    last_day = end.astimezone(OFFICE_TZ).date()
    while day <= last_day:
        local = datetime.combine(day, OPEN_AT, tzinfo=OFFICE_TZ)
        while local.time() < CLOSE_AT:
            starts_at = local.astimezone(UTC)
            ends_at = starts_at + SLOT_LENGTH
            if _is_office_slot(starts_at) and start <= starts_at and ends_at <= end:
                yield Slot(practitioner_ref=practitioner_ref, starts_at=starts_at, ends_at=ends_at)
            local += SLOT_LENGTH
        day += timedelta(days=1)


class MockHealthcareProvider(HealthcareProvider):
    """In-memory fake office. Create ONE per app, so all requests share the bookings."""

    def __init__(
        self,
        latency_ms: int = 0,
        failure_rate: float = 0.0,
        seed: int | None = None,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not 0.0 <= failure_rate <= 1.0:
            raise ValueError("failure_rate must be between 0.0 and 1.0")
        self._latency_seconds = latency_ms / 1000
        self._failure_rate = failure_rate
        self._random = random.Random(seed)  # a seed makes failures repeatable in tests
        self._now = now  # tests can pass a fixed "now"
        self._practitioners = {p.external_ref: p for p in PRACTITIONERS}
        self._bookings: dict[str, Booking] = {}
        # FastAPI runs normal endpoints in several threads; the lock stops two
        # requests from booking the same slot at the same moment.
        self._lock = threading.Lock()

    # ---------- HealthcareProvider methods ----------

    def list_practitioners(self) -> list[Practitioner]:
        self._simulate_network()
        return list(self._practitioners.values())

    def find_slots(self, practitioner_ref: str, start: datetime, end: datetime) -> list[Slot]:
        _require_aware(start, end)
        self._simulate_network()
        if practitioner_ref not in self._practitioners:
            return []
        now = self._now()
        with self._lock:
            taken = self._taken_starts(practitioner_ref)
        return [
            slot
            for slot in _office_slots(practitioner_ref, start, end)
            if slot.starts_at > now and slot.starts_at not in taken
        ]

    def book(self, practitioner_ref: str, starts_at: datetime, patient_ref: str) -> Booking:
        _require_aware(starts_at)
        self._simulate_network()
        starts_at = starts_at.astimezone(UTC)
        practitioner = self._practitioners.get(practitioner_ref)
        if practitioner is None or not _is_office_slot(starts_at) or starts_at <= self._now():
            raise SlotUnavailableError("No such slot.")
        with self._lock:
            if starts_at in self._taken_starts(practitioner_ref):
                raise SlotUnavailableError("Slot already booked.")
            booking = Booking(
                external_ref=f"mock-appt-{uuid.uuid4().hex[:12]}",
                practitioner_ref=practitioner_ref,
                starts_at=starts_at,
                ends_at=starts_at + SLOT_LENGTH,
                location=practitioner.location,
            )
            self._bookings[booking.external_ref] = booking
        return booking

    def cancel(self, booking_ref: str) -> None:
        self._simulate_network()
        with self._lock:
            if self._bookings.pop(booking_ref, None) is None:
                raise BookingNotFoundError("No such booking.")

    # ---------- Helpers ----------

    def _taken_starts(self, practitioner_ref: str) -> set[datetime]:
        """Start times already booked with this doctor. Call while holding the lock."""
        return {
            b.starts_at for b in self._bookings.values() if b.practitioner_ref == practitioner_ref
        }

    def _simulate_network(self) -> None:
        """Pretend to be a real remote system: maybe slow, maybe down."""
        if self._latency_seconds:
            sleep(self._latency_seconds)
        if self._failure_rate and self._random.random() < self._failure_rate:
            raise ProviderUnavailableError("Mock provider: simulated outage.")
