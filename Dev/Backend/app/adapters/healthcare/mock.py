"""In-memory mock provider (plan §6.2). Mock data only, never real patients.

Every practitioner works weekdays 9:00-12:00 and 13:00-16:30 clinic time in 30-minute
slots. About a quarter of the slots are "already taken" by other patients, chosen by a
hash so results are the same on every run. Latency and random failures are configurable
so the error paths can be exercised.
"""

import random
import time
import uuid
import zlib
from datetime import UTC, date, datetime, timedelta
from datetime import time as clock_time
from zoneinfo import ZoneInfo

from .base import ProviderUnavailable, Slot, SlotUnavailable, make_slot_id, parse_slot_id

WORKING_HOURS = ((clock_time(9, 0), clock_time(12, 0)), (clock_time(13, 0), clock_time(16, 30)))


class MockHealthcareProvider:
    def __init__(
        self,
        *,
        clinic_timezone: str = "America/Los_Angeles",
        slot_minutes: int = 30,
        latency_seconds: float = 0.0,
        failure_rate: float = 0.0,
        rng: random.Random | None = None,
    ) -> None:
        self.clinic_tz = ZoneInfo(clinic_timezone)
        self.slot_length = timedelta(minutes=slot_minutes)
        self.latency_seconds = latency_seconds
        self.failure_rate = failure_rate
        self._rng = rng or random.Random()
        self._bookings: dict[str, str] = {}  # booking ref -> slot id

    def search_slots(self, practitioner_ref: str, start: datetime, end: datetime) -> list[Slot]:
        self._simulate_network()
        booked = set(self._bookings.values())
        day = start.astimezone(self.clinic_tz).date()
        last_day = end.astimezone(self.clinic_tz).date()
        slots = []
        while day <= last_day:
            for slot in self._slots_on(practitioner_ref, day):
                if start <= slot.start < end and slot.id not in booked:
                    slots.append(slot)
            day += timedelta(days=1)
        return slots

    def book(self, slot_id: str, patient_ref: str) -> str:
        self._simulate_network()
        try:
            practitioner_ref, start = parse_slot_id(slot_id)
        except ValueError:
            raise SlotUnavailable(slot_id) from None
        if slot_id in self._bookings.values() or not self._is_open(practitioner_ref, start):
            raise SlotUnavailable(slot_id)
        booking_ref = f"mock-appt-{uuid.uuid4().hex[:12]}"
        self._bookings[booking_ref] = slot_id
        return booking_ref

    def cancel(self, booking_ref: str) -> None:
        self._simulate_network()
        self._bookings.pop(booking_ref, None)

    def _slots_on(self, practitioner_ref: str, day: date) -> list[Slot]:
        if day.weekday() >= 5:  # Saturday, Sunday
            return []
        slots = []
        for opens, closes in WORKING_HOURS:
            local = datetime.combine(day, opens, self.clinic_tz)
            closing = datetime.combine(day, closes, self.clinic_tz)
            while local + self.slot_length <= closing:
                start = local.astimezone(UTC)
                if not _taken_by_someone_else(practitioner_ref, start):
                    slots.append(
                        Slot(
                            id=make_slot_id(practitioner_ref, start),
                            practitioner_ref=practitioner_ref,
                            start=start,
                            end=start + self.slot_length,
                        )
                    )
                local += self.slot_length
        return slots

    def _is_open(self, practitioner_ref: str, start: datetime) -> bool:
        day = start.astimezone(self.clinic_tz).date()
        return any(slot.start == start for slot in self._slots_on(practitioner_ref, day))

    def _simulate_network(self) -> None:
        if self.latency_seconds:
            time.sleep(self.latency_seconds)
        if self.failure_rate and self._rng.random() < self.failure_rate:
            raise ProviderUnavailable("mock provider failure")


def _taken_by_someone_else(practitioner_ref: str, start: datetime) -> bool:
    return zlib.crc32(f"{practitioner_ref}{start:%Y%m%dT%H%M}".encode()) % 4 == 0
