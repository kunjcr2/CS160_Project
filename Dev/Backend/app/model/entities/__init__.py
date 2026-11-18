"""Import every model here so Alembic autogenerate sees them."""

from .appointment import Appointment, AppointmentReminder
from .base import Base
from .consent_grant import ConsentGrant
from .medication import Medication, MedicationReminder, MedicationSchedule
from .message import Message
from .pairing_code import PairingCode
from .pending_action import PendingAction
from .provider import Provider
from .refill_request import RefillRequest
from .session import Session
from .user import User

__all__ = [
    "Base",
    "User",
    "Session",
    "PairingCode",
    "Provider",
    "Appointment",
    "AppointmentReminder",
    "PendingAction",
    "ConsentGrant",
    "Medication",
    "MedicationSchedule",
    "MedicationReminder",
    "Message",
    "RefillRequest",
]
