"""A caregiver sets up an older adult's profile."""

from sqlalchemy.orm import Session as DbSession

from app.model.entities import ConsentGrant, User


class NotACaregiver(Exception):
    """Only caregivers can create older adult profiles."""


def create_older_adult(
    db: DbSession,
    *,
    caregiver: User,
    display_name: str,
    preferred_name: str | None,
    timezone: str,
    scopes: list[str],
) -> tuple[User, ConsentGrant]:
    """Create the profile AND a grant for the caregiver who made it.
    'profile:manage' is always added, so the caregiver can make a pairing code."""
    if caregiver.role != "caregiver":
        raise NotACaregiver()

    older_adult = User(
        role="older_adult",  # no email, no password: signs in with a pairing code
        display_name=display_name,
        preferred_name=preferred_name,
        timezone=timezone,
    )
    db.add(older_adult)
    db.flush()  # sends the INSERT now (not saved yet), so older_adult.id exists

    grant = ConsentGrant(
        older_adult_id=older_adult.id,
        caregiver_id=caregiver.id,
        scopes=sorted(set(scopes) | {"profile:manage"}),  # "|" joins two sets
    )
    db.add(grant)
    db.commit()  # saves both rows together, or neither
    return older_adult, grant
