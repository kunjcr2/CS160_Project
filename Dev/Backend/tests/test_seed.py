"""The seed script creates Margaret's story, and running it twice makes no duplicates."""

from sqlalchemy import func, select

from app.model.entities import ConsentGrant, Provider, User
from app.model.entities.consent_grant import SCOPES
from app.model.security import verify_password
from scripts.seed import DEMO_PASSWORD, seed_all


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def test_seed_creates_margarets_story(db):
    result = seed_all(db)
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
    seed_all(db)
    second = seed_all(db)
    assert second["providers_added"] == 0
    assert count(db, Provider) == 3
    assert count(db, User) == 3
    assert count(db, ConsentGrant) == 1


def test_demo_logins_use_the_demo_password(db):
    result = seed_all(db)
    for user in (result["caregiver"], result["agent"]):
        assert verify_password(DEMO_PASSWORD, user.password_hash)
