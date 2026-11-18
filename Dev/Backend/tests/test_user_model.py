"""Tests for the DB-level rules on the `users` table (plan §9)."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.model.entities import User


def _caregiver(**overrides):
    fields = {
        "role": "caregiver",
        "email": "caregiver@example.com",
        "password_hash": "hashed",
        "display_name": "A Caregiver",
    }
    fields.update(overrides)
    return User(**fields)


def test_caregiver_without_email_and_password_is_rejected(db):
    db.add(_caregiver(email=None, password_hash=None))
    with pytest.raises(IntegrityError):
        db.flush()


def test_older_adult_with_a_password_is_rejected(db):
    db.add(
        User(
            role="older_adult",
            password_hash="hashed",
            display_name="An Older Adult",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_invalid_role_is_rejected(db):
    db.add(_caregiver(role="superuser"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_speech_rate_out_of_range_is_rejected(db):
    db.add(_caregiver(speech_rate=3.0))
    with pytest.raises(IntegrityError):
        db.flush()


def test_uppercase_email_is_rejected(db):
    db.add(_caregiver(email="Caregiver@Example.com"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_duplicate_email_is_rejected(db):
    db.add(_caregiver())
    db.flush()
    db.add(_caregiver(display_name="Someone Else"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_valid_caregiver_and_older_adult_are_accepted(db):
    caregiver = _caregiver()
    older_adult = User(role="older_adult", display_name="An Older Adult")
    db.add_all([caregiver, older_adult])
    db.flush()  # no exception means every constraint was satisfied

    assert caregiver.email == "caregiver@example.com"
    assert older_adult.email is None
    assert older_adult.password_hash is None
