"""Queries for pending_actions. Every lookup filters by owner (plan §5.2)."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.model.entities import PendingAction, User


def lock_owned(session: Session, action_id: uuid.UUID, user_id: uuid.UUID) -> PendingAction | None:
    """Row-lock the action so two confirms (double tap, retry) run one after the other."""
    return session.scalar(
        select(PendingAction)
        .where(PendingAction.id == action_id, PendingAction.user_id == user_id)
        .with_for_update()
    )


def get_proposed(session: Session, user_id: uuid.UUID) -> PendingAction | None:
    return session.scalar(
        select(PendingAction).where(
            PendingAction.user_id == user_id, PendingAction.status == "proposed"
        )
    )


def lock_user(session: Session, user_id: uuid.UUID) -> None:
    """Serialize proposals per user, so replacing the old proposal and inserting the new
    one can't race with a second request (one proposed action per user, plan §5.3)."""
    session.execute(select(User.id).where(User.id == user_id).with_for_update())


def cancel_proposed(session: Session, user_id: uuid.UUID) -> None:
    session.execute(
        update(PendingAction)
        .where(PendingAction.user_id == user_id, PendingAction.status == "proposed")
        .values(status="cancelled")
    )
