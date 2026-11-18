"""Who may access whose data."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.model.entities import ConsentGrant, User


def can_access(db: DbSession, actor: User, older_adult_id: uuid.UUID, scope: str) -> bool:
    """True if `actor` may use `scope` on this older adult's data."""
    # Rule 1: an older adult can access ONLY their own data.
    if actor.role == "older_adult":
        return actor.id == older_adult_id

    # Rule 2: a caregiver needs an ACTIVE grant that INCLUDES this scope.
    if actor.role == "caregiver":
        grant_id = db.scalar(
            select(ConsentGrant.id).where(
                ConsentGrant.older_adult_id == older_adult_id,
                ConsentGrant.caregiver_id == actor.id,
                ConsentGrant.revoked_at.is_(None),
                ConsentGrant.scopes.contains([scope]),
            )
        )
        return grant_id is not None

    # Rule 3: support agents and admins get nothing here. Support agents will
    # see only their assigned handoff tickets (a later feature).
    return False
