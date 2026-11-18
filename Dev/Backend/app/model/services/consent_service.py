"""List and revoke consent grants."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session as DbSession

from app.model.entities import ConsentGrant, PairingCode, User


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
    # A revoked grant must not leave this caregiver a still-usable pairing
    # code: that code would otherwise hand them a fresh session anyway.
    _expire_unused_codes(db, older_adult_id=grant.older_adult_id, created_by=grant.caregiver_id)
    db.commit()


def _expire_unused_codes(
    db: DbSession, *, older_adult_id: uuid.UUID, created_by: uuid.UUID
) -> None:
    """Make this caregiver's still-usable codes for this older adult stop working."""
    now = datetime.now(UTC)
    db.execute(
        update(PairingCode)
        .where(
            PairingCode.older_adult_id == older_adult_id,
            PairingCode.created_by == created_by,
            PairingCode.used_at.is_(None),
            PairingCode.expires_at > now,
        )
        .values(expires_at=now)
    )
