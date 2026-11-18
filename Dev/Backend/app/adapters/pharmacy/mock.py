"""MockPharmacy: a fake pharmacy for development, tests, and the demo (PB-04).

- Every refill is accepted and given a made-up external id.
- Its status moves forward with time: `requested`, then `in_progress` after
  `in_progress_after`, then `ready` after `ready_after`.
- Slow calls and random failures can be turned on, like the other mocks.
- In-memory only: a restart forgets every request (refill_status() then returns None).

Mock/demo data only. Error texts here are for developers; user-facing sentences live in
views/messages.py.
"""

import random
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import sleep

from .interface import PharmacyProvider, PharmacyUnavailableError, RefillSubmission


def _utc_now() -> datetime:
    return datetime.now(UTC)


class MockPharmacy(PharmacyProvider):
    """In-memory fake pharmacy. Create ONE per app."""

    def __init__(
        self,
        latency_ms: int = 0,
        failure_rate: float = 0.0,
        seed: int | None = None,
        now: Callable[[], datetime] = _utc_now,
        in_progress_after: timedelta = timedelta(minutes=1),
        ready_after: timedelta = timedelta(minutes=30),
    ) -> None:
        if latency_ms < 0:
            raise ValueError("latency_ms must not be negative")
        if not 0.0 <= failure_rate <= 1.0:
            raise ValueError("failure_rate must be between 0.0 and 1.0")
        if not timedelta(0) <= in_progress_after <= ready_after:
            raise ValueError("need 0 <= in_progress_after <= ready_after")
        self._latency_seconds = latency_ms / 1000
        self._failure_rate = failure_rate
        self._random = random.Random(seed)  # a seed makes failures repeatable in tests
        self._now = now  # tests can pass a fake clock
        self._in_progress_after = in_progress_after
        self._ready_after = ready_after
        self._submitted: dict[str, datetime] = {}  # external_ref -> submitted_at

    def submit_refill(
        self, medication_name: str, dosage: str, *, patient_ref: str
    ) -> RefillSubmission:
        self._simulate_network()
        ref = f"mock-rx-{uuid.uuid4().hex[:12]}"
        submitted_at = self._now()
        self._submitted[ref] = submitted_at
        return RefillSubmission(external_ref=ref, submitted_at=submitted_at)

    def refill_status(self, external_ref: str) -> str | None:
        self._simulate_network()
        submitted_at = self._submitted.get(external_ref)
        if submitted_at is None:
            return None
        waited = self._now() - submitted_at
        if waited >= self._ready_after:
            return "ready"
        if waited >= self._in_progress_after:
            return "in_progress"
        return "requested"

    def _simulate_network(self) -> None:
        """Pretend to be a real remote system: maybe slow, maybe down."""
        if self._latency_seconds:
            sleep(self._latency_seconds)
        if self._failure_rate and self._random.random() < self._failure_rate:
            raise PharmacyUnavailableError("Mock pharmacy: simulated outage.")
