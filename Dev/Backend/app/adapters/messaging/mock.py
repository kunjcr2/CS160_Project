"""MockCareMessaging: a fake care-team messaging system for development, tests, and
the demo (PB-07, send only).

- Every send is accepted and given a made-up external id; nothing is actually
  delivered anywhere.
- Slow calls and random failures can be turned on to test error paths, the same
  way MockHealthcareProvider does.

Mock/demo data only. No real people, no real messages.
Error texts here are for developers; user-facing sentences live in views/messages.py.
"""

import random
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from time import sleep

from .interface import CareMessagingProvider, MessagingUnavailableError, SentMessage


def _utc_now() -> datetime:
    return datetime.now(UTC)


class MockCareMessaging(CareMessagingProvider):
    """In-memory fake messaging system. Create ONE per app."""

    def __init__(
        self,
        latency_ms: int = 0,
        failure_rate: float = 0.0,
        seed: int | None = None,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        if latency_ms < 0:
            raise ValueError("latency_ms must not be negative")
        if not 0.0 <= failure_rate <= 1.0:
            raise ValueError("failure_rate must be between 0.0 and 1.0")
        self._latency_seconds = latency_ms / 1000
        self._failure_rate = failure_rate
        self._random = random.Random(seed)  # a seed makes failures repeatable in tests
        self._now = now  # tests can pass a fixed "now"

    def send(self, recipient_ref: str, body: str, *, sender_ref: str) -> SentMessage:
        self._simulate_network()
        return SentMessage(external_ref=f"mock-msg-{uuid.uuid4().hex[:12]}", sent_at=self._now())

    def _simulate_network(self) -> None:
        """Pretend to be a real remote system: maybe slow, maybe down."""
        if self._latency_seconds:
            sleep(self._latency_seconds)
        if self._failure_rate and self._random.random() < self._failure_rate:
            raise MessagingUnavailableError("Mock messaging: simulated outage.")
