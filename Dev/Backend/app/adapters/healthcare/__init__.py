"""HealthcareProvider interface + mock implementation (FHIR-shaped, configurable
latency/failures).
"""

from .base import (
    HealthcareProvider,
    ProviderUnavailable,
    Slot,
    SlotUnavailable,
    make_slot_id,
    parse_slot_id,
)
from .mock import MockHealthcareProvider

# One shared instance, so bookings made through the mock are remembered while the
# process runs. Swap it with use_healthcare_provider() (tests, or a real adapter later).
_provider: HealthcareProvider = MockHealthcareProvider()


def get_healthcare_provider() -> HealthcareProvider:
    return _provider


def use_healthcare_provider(provider: HealthcareProvider) -> None:
    global _provider
    _provider = provider


__all__ = [
    "HealthcareProvider",
    "MockHealthcareProvider",
    "ProviderUnavailable",
    "Slot",
    "SlotUnavailable",
    "get_healthcare_provider",
    "make_slot_id",
    "parse_slot_id",
    "use_healthcare_provider",
]
