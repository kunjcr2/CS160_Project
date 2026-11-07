"""Seed demo data: Margaret's story. Mock/demo data only, never real patients.

Run from Dev/Backend after migrations:  python -m scripts.seed
Safe to run many times: rows that already exist are kept, not duplicated.

Not seeded yet (their tables don't exist): Margaret's 4 medications and her pharmacy.
TODO: add them in S2-06 (medications) and when the contacts table is built.
Free appointment slots are not seeded: the mock doctor's office makes them.
"""

import os

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.adapters.healthcare.mock import PRACTITIONERS
from app.db import SessionLocal, engine
from app.model.entities import ConsentGrant, Provider, User
from app.model.entities.consent_grant import SCOPES
from app.model.security import hash_password
from app.model.services.older_adult_service import create_older_adult

# Demo-only password for the demo logins (local laptops only). Change it with SEED_PASSWORD.
DEMO_PASSWORD = os.environ.get("SEED_PASSWORD", "demo-password-2026")

# example.com is reserved for examples, so these never belong to a real person.
CAREGIVER_EMAIL = "daniel.lee@example.com"
AGENT_EMAIL = "riley.chen@example.com"
MARGARET_NAME = "Margaret Lee"


class SeedRoleMismatch(Exception):
    """An email the seed script wants to use already belongs to a different role."""


def seed_providers(db: DbSession) -> tuple[int, int]:
    """Copy the mock's doctors into the providers table, updating any that changed.
    Returns (added, updated)."""
    added = updated = 0
    for doctor in PRACTITIONERS:
        existing = db.scalar(select(Provider).where(Provider.external_ref == doctor.external_ref))
        if existing is None:
            db.add(
                Provider(
                    external_ref=doctor.external_ref,
                    name=doctor.name,
                    specialty=doctor.specialty,
                    location=doctor.location,
                    phone=doctor.phone,
                )
            )
            added += 1
            continue
        if (existing.name, existing.specialty, existing.location, existing.phone) != (
            doctor.name,
            doctor.specialty,
            doctor.location,
            doctor.phone,
        ):
            existing.name = doctor.name
            existing.specialty = doctor.specialty
            existing.location = doctor.location
            existing.phone = doctor.phone
            updated += 1
    db.commit()
    return added, updated


def get_or_create_login_user(
    db: DbSession, *, role: str, email: str, display_name: str
) -> tuple[User, bool]:
    """Find a user by email, or create one with the demo password.

    Returns (user, created). Raises SeedRoleMismatch if the email already belongs
    to a user with a different role: reusing it would sign that person in as the
    wrong role, or silently fail to make the demo account this script promises.
    """
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        if user.role != role:
            raise SeedRoleMismatch(
                f"{email} already exists with role {user.role!r}, expected {role!r}."
            )
        return user, False
    user = User(
        role=role,
        email=email,
        password_hash=hash_password(DEMO_PASSWORD),
        display_name=display_name,
    )
    db.add(user)
    db.commit()
    return user, True


def get_or_create_margaret(db: DbSession, caregiver: User) -> User:
    """Find Margaret through her son's grant, or create her with the normal service."""
    margaret = db.scalar(
        select(User)
        .join(ConsentGrant, ConsentGrant.older_adult_id == User.id)
        .where(ConsentGrant.caregiver_id == caregiver.id, User.display_name == MARGARET_NAME)
    )
    if margaret is None:
        margaret, _grant = create_older_adult(
            db,
            caregiver=caregiver,
            display_name=MARGARET_NAME,
            preferred_name="Maggie",
            timezone="America/Los_Angeles",
            scopes=list(SCOPES),  # her son may see and manage everything allowed
        )
    return margaret


def seed_all(db: DbSession) -> dict:
    """Create the whole demo story. Returns the main people (used by tests)."""
    providers_added, providers_updated = seed_providers(db)
    caregiver, caregiver_created = get_or_create_login_user(
        db, role="caregiver", email=CAREGIVER_EMAIL, display_name="Daniel Lee"
    )
    agent, agent_created = get_or_create_login_user(
        db, role="support_agent", email=AGENT_EMAIL, display_name="Riley Chen"
    )
    margaret = get_or_create_margaret(db, caregiver)
    return {
        "providers_added": providers_added,
        "providers_updated": providers_updated,
        "caregiver": caregiver,
        "caregiver_created": caregiver_created,
        "agent": agent,
        "agent_created": agent_created,
        "margaret": margaret,
    }


def main() -> None:
    print(f"Seeding database: {engine.url.database}")
    with SessionLocal() as db:
        result = seed_all(db)
    print(
        f"  Providers added: {result['providers_added']}, "
        f"updated: {result['providers_updated']} (0/0 = already up to date)"
    )
    print(f"  Margaret (older adult) id: {result['margaret'].id}")
    for label, email, created in (
        ("Caregiver", CAREGIVER_EMAIL, result["caregiver_created"]),
        ("Support agent", AGENT_EMAIL, result["agent_created"]),
    ):
        if created:
            print(f"  {label} login: {email}, password: {DEMO_PASSWORD!r} (just created)")
        else:
            print(f"  {label} login: {email}, already existed: password unchanged")


if __name__ == "__main__":
    main()
