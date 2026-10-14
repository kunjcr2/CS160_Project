"""Provider, slot, and appointment response models (PB-01)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.model.entities import Appointment, Provider, User
from app.model.services.appointment_service import SlotOption
from app.views.formatting import spoken_date_time


class ProviderOut(BaseModel):
    id: uuid.UUID
    name: str
    specialty: str
    location: str
    phone: str | None

    @classmethod
    def from_entity(cls, provider: Provider) -> "ProviderOut":
        return cls.model_validate(provider, from_attributes=True)


class SlotOut(BaseModel):
    slot_id: str  # propose with {"action_type": "book_appointment", "payload": {"slot_id": ...}}
    provider: ProviderOut
    starts_at: datetime  # UTC
    ends_at: datetime
    label: str  # "Tuesday, October 20 at 10:30 AM" in the user's time zone

    @classmethod
    def from_option(cls, option: SlotOption, user: User) -> "SlotOut":
        return cls(
            slot_id=option.slot_id,
            provider=ProviderOut.from_entity(option.provider),
            starts_at=option.starts_at,
            ends_at=option.ends_at,
            label=spoken_date_time(option.starts_at, user.timezone),
        )


class AppointmentOut(BaseModel):
    id: uuid.UUID
    provider: ProviderOut
    starts_at: datetime  # UTC
    ends_at: datetime
    location: str
    status: str  # booked, cancelled, completed
    label: str  # in the user's time zone

    @classmethod
    def from_entity(cls, appointment: Appointment, provider: Provider, user: User):
        return cls(
            id=appointment.id,
            provider=ProviderOut.from_entity(provider),
            starts_at=appointment.starts_at,
            ends_at=appointment.ends_at,
            location=appointment.location,
            status=appointment.status,
            label=spoken_date_time(appointment.starts_at, user.timezone),
        )
