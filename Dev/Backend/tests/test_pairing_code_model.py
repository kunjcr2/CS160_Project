"""Tests for the DB-level rule on pairing_codes.code_hash: unique only among
codes still usable, so a dead (already-used) code can't block a new one."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.model.entities import PairingCode, User
from app.model.security import hash_password

SAME_HASH = "a" * 64


@pytest.fixture
def older_adult(db):
    user = User(role="older_adult", display_name="An Older Adult")
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def caregiver(db):
    user = User(
        role="caregiver",
        email="caregiver@example.com",
        password_hash=hash_password("correct horse battery"),
        display_name="A Caregiver",
    )
    db.add(user)
    db.flush()
    return user


def _code(older_adult, caregiver, **overrides):
    fields = {
        "code_hash": SAME_HASH,
        "older_adult_id": older_adult.id,
        "created_by": caregiver.id,
        "expires_at": datetime.now(UTC) + timedelta(minutes=15),
    }
    fields.update(overrides)
    return PairingCode(**fields)


def test_two_unused_codes_with_the_same_hash_are_rejected(db, older_adult, caregiver):
    db.add(_code(older_adult, caregiver))
    db.flush()
    db.add(_code(older_adult, caregiver))
    with pytest.raises(IntegrityError):
        db.flush()


def test_a_used_codes_hash_can_be_reused_by_a_new_code(db, older_adult, caregiver):
    used_up = _code(older_adult, caregiver, used_at=datetime.now(UTC))
    db.add(used_up)
    db.flush()

    db.add(_code(older_adult, caregiver))  # same hash, but the old one is already used
    db.flush()  # no exception
