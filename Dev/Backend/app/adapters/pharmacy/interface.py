"""PharmacyProvider: what any pharmacy system must do for refills (PB-04).

The model (services and commands) talks ONLY to this interface, never to a real or
mock system directly. Today the only implementation is MockPharmacy (mock.py).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

# The order a refill moves through at the pharmacy (plan §8 PB-04).
REFILL_PROGRESS = ("requested", "in_progress", "ready")


class PharmacyError(Exception):
    """Base class for every error from a pharmacy system."""


class PharmacyUnavailableError(PharmacyError):
    """The pharmacy system is down or too slow. Safe to try again later."""


@dataclass(frozen=True)
class RefillSubmission:
    """A refill request accepted by the pharmacy."""

    external_ref: str  # this request's id in the pharmacy system
    submitted_at: datetime  # UTC


class PharmacyProvider(ABC):
    """What every pharmacy system must be able to do. Every method can raise
    PharmacyUnavailableError."""

    @abstractmethod
    def submit_refill(
        self, medication_name: str, dosage: str, *, patient_ref: str
    ) -> RefillSubmission:
        """Ask the pharmacy to refill this medication. patient_ref is our user's id as text."""

    @abstractmethod
    def refill_status(self, external_ref: str) -> str | None:
        """One of REFILL_PROGRESS, or None if the pharmacy doesn't know this request
        (the mock forgets everything on restart; our database keeps the last status)."""
