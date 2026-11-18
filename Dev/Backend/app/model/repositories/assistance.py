"""Queries for human assistance requests (PB-06)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model.entities import AssistanceRequest
from app.model.entities.assistance_request import OPEN_ASSISTANCE_STATUSES


def open_for_user(session: Session, older_adult_id: uuid.UUID) -> AssistanceRequest | None:
    """This older adult's unresolved request, if any."""
    return session.scalar(
        select(AssistanceRequest).where(
            AssistanceRequest.user_id == older_adult_id,
            AssistanceRequest.status.in_(OPEN_ASSISTANCE_STATUSES),
        )
    )


def queue(session: Session) -> list[AssistanceRequest]:
    """Every unresolved request, oldest first (first come, first served)."""
    return list(
        session.scalars(
            select(AssistanceRequest)
            .where(AssistanceRequest.status.in_(OPEN_ASSISTANCE_STATUSES))
            .order_by(AssistanceRequest.created_at)
        )
    )


def lock(session: Session, request_id: uuid.UUID) -> AssistanceRequest | None:
    """The request, locked until commit, so two agents can't both take it."""
    return session.scalar(
        select(AssistanceRequest).where(AssistanceRequest.id == request_id).with_for_update()
    )
