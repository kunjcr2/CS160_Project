"""The seed script creates Margaret's story, and running it twice makes no duplicates."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.model.entities import (
    ConsentGrant,
    Medication,
    MedicationReminder,
    MedicationSchedule,
    Provider,
    User,
)
from app.model.entities.consent_grant import SCOPES
from app.model.security import hash_password, verify_password
from scripts.seed import (
    CAREGIVER_EMAIL,
    DEMO_PASSWORD,
    SeedRoleMismatch,
    get_or_create_login_user,
    seed_all,
    seed_providers,
)

# Fixed "now": Sunday, Oct 18, 2026, 06:00 in California (before the first 08:00 dose).
NOW = datetime(2026, 10, 18, 6, 0, tzinfo=ZoneInfo("America/Los_Angeles"))


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def test_seed_creates_margarets_story(db):
    result = seed_all(db, now=NOW)
    margaret = result["margaret"]

    assert count(db, Provider) == 3
    assert count(db, User) == 3  # Margaret, her son, the support agent
    assert margaret.role == "older_adult"
    assert margaret.email is None  # older adults sign in with a pairing code
    assert margaret.preferred_name == "Maggie"
    assert result["agent"].role == "support_agent"

    grant = db.scalar(select(ConsentGrant).where(ConsentGrant.older_adult_id == margaret.id))
    assert grant.caregiver_id == result["caregiver"].id
    assert sorted(grant.scopes) == sorted(SCOPES)


def test_seed_twice_makes_no_duplicates(db):
    seed_all(db, now=NOW)
    second = seed_all(db, now=NOW)
    assert second["providers_added"] == 0
    assert count(db, Provider) == 3
    assert count(db, User) == 3
    assert count(db, ConsentGrant) == 1


def test_demo_logins_use_the_demo_password(db):
    result = seed_all(db, now=NOW)
    for user in (result["caregiver"], result["agent"]):
        assert verify_password(DEMO_PASSWORD, user.password_hash)


def test_seed_gives_margaret_four_medications(db):
    result = seed_all(db, now=NOW)
    margaret = result["margaret"]
    names = set(db.scalars(select(Medication.name).where(Medication.user_id == margaret.id)))
    assert names == {"Lisinopril", "Metformin", "Carvedilol", "Atorvastatin"}
    assert count(db, MedicationSchedule) == 6  # two are twice a day: 1 + 2 + 2 + 1
    assert result["doses_added"] == 42  # 6 doses a day x 7 days
    atorvastatin = db.scalar(select(Medication).where(Medication.name == "Atorvastatin"))
    assert atorvastatin.refills_remaining == 0  # for the PB-04 "no refills" demo


def test_seed_twice_makes_no_duplicate_medications_or_doses(db):
    seed_all(db, now=NOW)
    second = seed_all(db, now=NOW)
    assert (second["medications_added"], second["doses_added"]) == (0, 0)
    assert count(db, Medication) == 4
    assert count(db, MedicationReminder) == 42


def test_caregiver_email_with_a_different_role_is_rejected(db):
    db.add(
        User(
            role="support_agent",
            email=CAREGIVER_EMAIL,
            password_hash=hash_password("some password"),
            display_name="Someone Else",
        )
    )
    db.commit()
    with pytest.raises(SeedRoleMismatch):
        get_or_create_login_user(
            db, role="caregiver", email=CAREGIVER_EMAIL, display_name="Daniel Lee"
        )


def test_seed_providers_updates_changed_fields(db):
    seed_providers(db)
    doctor = db.scalar(select(Provider))
    doctor.specialty = "Something Else"
    db.commit()

    added, updated = seed_providers(db)

    assert added == 0
    assert updated == 1
    db.refresh(doctor)
    assert doctor.specialty != "Something Else"


def test_seed_providers_leaves_unchanged_rows_alone(db):
    seed_providers(db)
    added, updated = seed_providers(db)
    assert (added, updated) == (0, 0)
