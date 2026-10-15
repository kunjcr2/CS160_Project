"""The seed script creates Margaret's story, and running it twice makes no duplicates."""

from datetime import datetime
from zoneinfo import ZoneInfo

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
from app.model.security import verify_password
from scripts.seed import DEMO_PASSWORD, seed_all

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
