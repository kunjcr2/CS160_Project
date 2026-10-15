"""Seed demo data: Margaret's story. Mock/demo data only, never real patients.

Run from Dev/Backend after migrations:  python -m scripts.seed
Safe to run many times: rows that already exist are kept, not duplicated.

Margaret takes 4 medications (2 of them twice a day). Each run also creates any missing
doses for the next days, so a demo laptop can simply run the seed again to top them up.
The medicines are a made-up demo list, not medical advice.

Not seeded yet: her pharmacy (TODO: when the contacts table is built, PB-04).
Free appointment slots are not seeded: the mock doctor's office makes them.
"""

import os
from datetime import UTC, datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.adapters.healthcare.mock import PRACTITIONERS
from app.db import SessionLocal, engine
from app.model.entities import ConsentGrant, Medication, MedicationReminder, Provider, User
from app.model.entities.consent_grant import SCOPES
from app.model.entities.medication import EVERY_DAY
from app.model.security import hash_password
from app.model.services.medication_service import create_medication, generate_doses
from app.model.services.older_adult_service import create_older_adult

# Demo-only password for the demo logins (local laptops only). Change it with SEED_PASSWORD.
DEMO_PASSWORD = os.environ.get("SEED_PASSWORD", "demo-password-2026")

# example.com is reserved for examples, so these never belong to a real person.
CAREGIVER_EMAIL = "daniel.lee@example.com"
AGENT_EMAIL = "riley.chen@example.com"
MARGARET_NAME = "Margaret Lee"

# Margaret's medicines (plan §6.12: four medications, two of them twice daily).
# Times are her LOCAL time. Atorvastatin has 0 refills on purpose, to demo PB-04's
# "no refills remaining" case later.
MARGARET_MEDICATIONS = [
    {
        "name": "Lisinopril",
        "dosage": "10 mg",
        "instructions": "For blood pressure",
        "refills_remaining": 2,
        "times": ["08:00"],
    },
    {
        "name": "Metformin",
        "dosage": "500 mg",
        "instructions": "Take with food",
        "refills_remaining": 3,
        "times": ["08:00", "20:00"],
    },
    {
        "name": "Carvedilol",
        "dosage": "6.25 mg",
        "instructions": "Take with food",
        "refills_remaining": 1,
        "times": ["08:00", "20:00"],
    },
    {
        "name": "Atorvastatin",
        "dosage": "20 mg",
        "instructions": "Take in the evening",
        "refills_remaining": 0,
        "times": ["20:00"],
    },
]


def seed_providers(db: DbSession) -> int:
    """Copy the mock's doctors into the providers table. Returns how many were added."""
    added = 0
    for doctor in PRACTITIONERS:
        exists = db.scalar(select(Provider).where(Provider.external_ref == doctor.external_ref))
        if exists is None:
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
    db.commit()
    return added


def get_or_create_login_user(db: DbSession, *, role: str, email: str, display_name: str) -> User:
    """Find a user by email, or create one with the demo password."""
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            role=role,
            email=email,
            password_hash=hash_password(DEMO_PASSWORD),
            display_name=display_name,
        )
        db.add(user)
        db.commit()
    return user


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


def seed_medications(db: DbSession, margaret: User, now: datetime) -> tuple[int, int]:
    """Add Margaret's missing medications, then her missing doses for the next days.

    Returns (medications added, doses added). Uses the normal medication service,
    so the seed follows exactly the same rules as the app.
    """
    doses_before = _count_doses(db, margaret)
    have = set(db.scalars(select(Medication.name).where(Medication.user_id == margaret.id)))
    medications_added = 0
    for medicine in MARGARET_MEDICATIONS:
        if medicine["name"] in have:
            continue
        create_medication(
            db,
            margaret.id,
            name=medicine["name"],
            dosage=medicine["dosage"],
            instructions=medicine["instructions"],
            refills_remaining=medicine["refills_remaining"],
            schedules=[(time.fromisoformat(t), list(EVERY_DAY)) for t in medicine["times"]],
            now=now,
        )
        medications_added += 1
    # Tops up doses on every run (e.g. a new day has started since the last seed).
    generate_doses(db, now, user_id=margaret.id)
    doses_added = _count_doses(db, margaret) - doses_before
    db.commit()
    return medications_added, doses_added


def _count_doses(db: DbSession, margaret: User) -> int:
    return db.scalar(select(func.count()).where(MedicationReminder.user_id == margaret.id))


def seed_all(db: DbSession, now: datetime | None = None) -> dict:
    """Create the whole demo story. Returns the main people (used by tests).

    now: the current time (tests pass a fixed one so the dose count is always the same).
    """
    now = now or datetime.now(UTC)
    providers_added = seed_providers(db)
    caregiver = get_or_create_login_user(
        db, role="caregiver", email=CAREGIVER_EMAIL, display_name="Daniel Lee"
    )
    agent = get_or_create_login_user(
        db, role="support_agent", email=AGENT_EMAIL, display_name="Riley Chen"
    )
    margaret = get_or_create_margaret(db, caregiver)
    medications_added, doses_added = seed_medications(db, margaret, now)
    return {
        "providers_added": providers_added,
        "medications_added": medications_added,
        "doses_added": doses_added,
        "caregiver": caregiver,
        "agent": agent,
        "margaret": margaret,
    }


def main() -> None:
    print(f"Seeding database: {engine.url.database}")
    with SessionLocal() as db:
        result = seed_all(db)
    print(f"  Providers added: {result['providers_added']} (0 = already there)")
    print(f"  Margaret (older adult) id: {result['margaret'].id}")
    print(f"  Medications added: {result['medications_added']} (0 = already there)")
    print(f"  Doses added: {result['doses_added']} (next days, missing ones only)")
    print(f"  Caregiver login: {CAREGIVER_EMAIL}")
    print(f"  Support agent login: {AGENT_EMAIL}")
    print("  Password for both: the DEMO_PASSWORD in scripts/seed.py")


if __name__ == "__main__":
    main()
