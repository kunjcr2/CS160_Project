"""Appointment reads and slot search (PB-01). Booking itself is the BookAppointment command,
so it can only happen through confirmation (plan §5.3)."""

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.adapters.healthcare import HealthcareProvider, get_healthcare_provider
from app.model.entities import Appointment, Provider, User
from app.model.repositories import appointments as repo

MAX_OPTIONS = 3  # plan §8 PB-01: present at most three slots at a time


@dataclass(frozen=True)
class SlotOption:
    slot_id: str  # pass to propose("book_appointment", {"slot_id": ...})
    provider: Provider
    starts_at: datetime  # UTC
    ends_at: datetime


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _name_tokens(name: str) -> set[str]:
    words = re.findall(r"[a-z]+", name.lower())
    return {word for word in words if word not in {"dr", "doctor"}}


class AppointmentService:
    def __init__(
        self,
        session: Session,
        *,
        provider_api: HealthcareProvider | None = None,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.session = session
        self.provider_api = provider_api or get_healthcare_provider()
        self.clock = clock

    def find_providers(self, name: str | None = None) -> list[Provider]:
        """All providers, or those whose name contains every word of `name`
        ("Dr. Chen" matches "Dr. Lisa Chen"). More than one match means: ask which one."""
        providers = repo.all_providers(self.session)
        if not name:
            return providers
        wanted = _name_tokens(name)
        return [p for p in providers if wanted and wanted <= _name_tokens(p.name)]

    def find_slots(
        self,
        user: User,
        provider: Provider,
        date_from: date,
        date_to: date,
        *,
        limit: int = MAX_OPTIONS,
    ) -> list[SlotOption]:
        """Free slots between two dates (inclusive) in the USER's time zone, earliest first.
        Skips slots in the past and slots already booked through us."""
        tz = ZoneInfo(user.timezone)
        start = max(datetime.combine(date_from, time.min, tz), self.clock())
        end = datetime.combine(date_to + timedelta(days=1), time.min, tz)
        if start >= end:
            return []
        taken = repo.booked_starts(self.session, provider.id, start, end)
        options = []
        for slot in self.provider_api.search_slots(provider.external_ref, start, end):
            if slot.start not in taken:
                options.append(SlotOption(slot.id, provider, slot.start, slot.end))
            if len(options) == limit:
                break
        return options

    def upcoming(self, user: User) -> list[Appointment]:
        return repo.upcoming_for_user(self.session, user.id, self.clock())

    def get(self, user: User, appointment_id: uuid.UUID) -> Appointment | None:
        return repo.get_owned(self.session, appointment_id, user.id)
