"""Queries for refill requests and the medications they're for. Filter by the older adult
they're about (plan §5.2)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model.entities import Medication, RefillRequest
from app.model.entities.refill_request import OPEN_REFILL_STATUSES


def active_medications(session: Session, older_adult_id: uuid.UUID) -> list[Medication]:
    """Medications this older adult still takes (not stopped), by name."""
    return list(
        session.scalars(
            select(Medication)
            .where(Medication.user_id == older_adult_id, Medication.stopped_at.is_(None))
            .order_by(Medication.name)
        )
    )


def lock_medication(session: Session, medication_id: uuid.UUID) -> Medication | None:
    """The medication row, locked until commit, so two confirms can't both use the last
    refill."""
    return session.scalar(
        select(Medication).where(Medication.id == medication_id).with_for_update()
    )


def open_request(session: Session, medication_id: uuid.UUID) -> RefillRequest | None:
    return session.scalar(
        select(RefillRequest).where(
            RefillRequest.medication_id == medication_id,
            RefillRequest.status.in_(OPEN_REFILL_STATUSES),
        )
    )


def for_older_adult(session: Session, older_adult_id: uuid.UUID) -> list[RefillRequest]:
    """This older adult's refill requests, newest first."""
    return list(
        session.scalars(
            select(RefillRequest)
            .where(RefillRequest.user_id == older_adult_id)
            .order_by(RefillRequest.created_at.desc())
        )
    )
