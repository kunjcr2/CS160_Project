"""List and revoke consent grants."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DbSession

from app.model.entities import ConsentGrant, User


class GrantNotFound(Exception):
    """No such grant, or it isn't yours (we don't say which)."""


def _mine(user: User):
    """WHERE rule: grants where I am the caregiver OR the older adult."""
    return or_(ConsentGrant.caregiver_id == user.id, ConsentGrant.older_adult_id == user.id)


def list_active_grants(db: DbSession, user: User) -> list[ConsentGrant]:
    query = (
        select(ConsentGrant)
        .where(_mine(user), ConsentGrant.revoked_at.is_(None))
        .order_by(ConsentGrant.created_at)
    )
    return list(db.scalars(query))


def revoke_grant(db: DbSession, user: User, grant_id: uuid.UUID) -> None:
    """Either side of the grant can end it.
    We search by id AND owner together, never by id alone."""
    grant = db.scalar(
        select(ConsentGrant).where(
            ConsentGrant.id == grant_id, _mine(user), ConsentGrant.revoked_at.is_(None)
        )
    )
    if grant is None:
        raise GrantNotFound()
    grant.revoked_at = datetime.now(UTC)
    db.commit()
