"""Permission tests (S2-04, S2-07): nobody sees data they shouldn't."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.model.entities import ConsentGrant, User
from app.model.permissions import can_access


def make_user(db, role, name):
    """Save a user straight to the database (no login needed for these tests)."""
    needs_login = role != "older_adult"
    user = User(
        role=role,
        display_name=name,
        email=f"{name.lower()}@example.com" if needs_login else None,
        password_hash="not-a-real-hash" if needs_login else None,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def margaret(db):
    return make_user(db, "older_adult", "Margaret")


@pytest.fixture
def other_adult(db):
    return make_user(db, "older_adult", "Walter")


@pytest.fixture
def carer(db):
    return make_user(db, "caregiver", "Carer")


@pytest.fixture
def grant(db, margaret, carer):
    """Carer may read Margaret's appointments, and nothing else."""
    grant = ConsentGrant(
        older_adult_id=margaret.id, caregiver_id=carer.id, scopes=["appointments:read"]
    )
    db.add(grant)
    db.commit()
    return grant


# ---------- Older adults ----------


def test_older_adult_can_access_own_data(db, margaret):
    assert can_access(db, margaret, margaret.id, "appointments:read")


def test_older_adult_cannot_access_someone_else(db, margaret, other_adult):
    assert not can_access(db, margaret, other_adult.id, "appointments:read")


# ---------- Caregivers ----------


def test_caregiver_with_grant_and_scope_can_access(db, margaret, carer, grant):
    assert can_access(db, carer, margaret.id, "appointments:read")


def test_caregiver_cannot_use_a_scope_not_granted(db, margaret, carer, grant):
    assert not can_access(db, carer, margaret.id, "medications:read")


def test_caregiver_without_grant_cannot_access(db, margaret, carer):
    assert not can_access(db, carer, margaret.id, "appointments:read")


def test_revoked_grant_gives_no_access(db, margaret, carer, grant):
    from datetime import UTC, datetime

    grant.revoked_at = datetime.now(UTC)
    db.commit()
    assert not can_access(db, carer, margaret.id, "appointments:read")


def test_support_agent_cannot_access_user_data(db, margaret):
    agent = make_user(db, "support_agent", "Agent")
    assert not can_access(db, agent, margaret.id, "appointments:read")


# ---------- Database rules ----------


def test_database_rejects_unknown_scope(db, margaret, carer):
    db.add(
        ConsentGrant(
            older_adult_id=margaret.id, caregiver_id=carer.id, scopes=["conversations:read"]
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_database_rejects_second_active_grant_for_same_pair(db, margaret, carer, grant):
    db.add(
        ConsentGrant(older_adult_id=margaret.id, caregiver_id=carer.id, scopes=["medications:read"])
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_database_rejects_grant_to_yourself(db, carer):
    db.add(ConsentGrant(older_adult_id=carer.id, caregiver_id=carer.id, scopes=["profile:manage"]))
    with pytest.raises(IntegrityError):
        db.commit()
