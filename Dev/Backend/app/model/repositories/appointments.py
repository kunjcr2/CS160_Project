"""Queries for providers and appointments. Appointment lookups filter by owner (plan §5.2)."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model.entities import Appointment, Provider


def all_providers(session: Session) -> list[Provider]:
    return list(session.scalars(select(Provider).order_by(Provider.name)))


def provider_by_ref(session: Session, external_ref: str) -> Provider | None:
    return session.scalar(select(Provider).where(Provider.external_ref == external_ref))


def booked_starts(
    session: Session, provider_id: uuid.UUID, start: datetime, end: datetime
) -> set[datetime]:
    """Start times already booked through us for this provider (any patient)."""
    return set(
        session.scalars(
            select(Appointment.starts_at).where(
                Appointment.provider_id == provider_id,
                Appointment.status == "booked",
                Appointment.starts_at >= start,
                Appointment.starts_at < end,
            )
        )
    )


def upcoming_for_user(session: Session, user_id: uuid.UUID, now: datetime) -> list[Appointment]:
    return list(
        session.scalars(
            select(Appointment)
            .where(
                Appointment.user_id == user_id,
                Appointment.status == "booked",
                Appointment.ends_at > now,
            )
            .order_by(Appointment.starts_at)
        )
    )


def get_owned(
    session: Session, appointment_id: uuid.UUID, user_id: uuid.UUID
) -> Appointment | None:
    return session.scalar(
        select(Appointment).where(Appointment.id == appointment_id, Appointment.user_id == user_id)
    )
