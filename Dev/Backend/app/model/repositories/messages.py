"""Queries for care-team messages. Filters by the older adult they're about (plan §5.2)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model.entities import Message


def for_older_adult(session: Session, older_adult_id: uuid.UUID) -> list[Message]:
    """This older adult's messages, newest first."""
    return list(
        session.scalars(
            select(Message)
            .where(Message.older_adult_id == older_adult_id)
            .order_by(Message.created_at.desc())
        )
    )
