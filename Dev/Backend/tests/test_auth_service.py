"""Tests for register, login, refresh, logout."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.model.entities import Session
from app.model.security import hash_token
from app.model.services import auth_service
from app.model.services.auth_service import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidRefreshToken,
)

PASSWORD = "correct horse battery"


@pytest.fixture
def caregiver(db):
    """A registered caregiver, ready to log in."""
    return auth_service.register_caregiver(
        db, email="Carer@Example.com", password=PASSWORD, display_name="Test Carer"
    )


# ---------- Register ----------


def test_register_saves_lowercase_email_and_hashed_password(caregiver):
    assert caregiver.email == "carer@example.com"
    assert caregiver.role == "caregiver"
    assert caregiver.password_hash != PASSWORD


def test_register_same_email_twice_fails(db, caregiver):
    with pytest.raises(EmailAlreadyRegistered):
        auth_service.register_caregiver(
            db, email="CARER@example.com", password="other password", display_name="Copy"
        )


# ---------- Login ----------


def test_login_with_right_password_gives_tokens(db, caregiver):
    result = auth_service.login(db, email="carer@example.com", password=PASSWORD)
    assert result.user.id == caregiver.id
    assert result.access_token
    assert result.refresh_token


def test_login_saves_only_the_hash_of_the_refresh_token(db, caregiver):
    result = auth_service.login(db, email="carer@example.com", password=PASSWORD)
    saved = db.scalars(select(Session)).all()
    assert len(saved) == 1
    assert saved[0].refresh_token_hash == hash_token(result.refresh_token)
    assert saved[0].refresh_token_hash != result.refresh_token


def test_login_with_wrong_password_fails(db, caregiver):
    with pytest.raises(InvalidCredentials):
        auth_service.login(db, email="carer@example.com", password="wrong")


def test_login_with_unknown_email_fails(db):
    with pytest.raises(InvalidCredentials):
        auth_service.login(db, email="nobody@example.com", password=PASSWORD)


# ---------- Refresh ----------


def test_refresh_gives_new_tokens(db, caregiver):
    first = auth_service.login(db, email="carer@example.com", password=PASSWORD)
    second = auth_service.refresh(db, first.refresh_token)
    assert second.refresh_token != first.refresh_token
    assert second.user.id == caregiver.id


def test_old_refresh_token_stops_working_after_refresh(db, caregiver):
    first = auth_service.login(db, email="carer@example.com", password=PASSWORD)
    auth_service.refresh(db, first.refresh_token)
    with pytest.raises(InvalidRefreshToken):
        auth_service.refresh(db, first.refresh_token)


def test_refresh_with_unknown_token_fails(db):
    with pytest.raises(InvalidRefreshToken):
        auth_service.refresh(db, "not-a-real-token")


def test_refresh_with_expired_session_fails(db, caregiver):
    result = auth_service.login(db, email="carer@example.com", password=PASSWORD)
    saved = db.scalar(select(Session))
    saved.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    with pytest.raises(InvalidRefreshToken):
        auth_service.refresh(db, result.refresh_token)


# ---------- Logout ----------


def test_refresh_fails_after_logout(db, caregiver):
    result = auth_service.login(db, email="carer@example.com", password=PASSWORD)
    auth_service.logout(db, result.refresh_token)
    with pytest.raises(InvalidRefreshToken):
        auth_service.refresh(db, result.refresh_token)


def test_logout_twice_is_fine(db, caregiver):
    result = auth_service.login(db, email="carer@example.com", password=PASSWORD)
    auth_service.logout(db, result.refresh_token)
    auth_service.logout(db, result.refresh_token)  # no error
