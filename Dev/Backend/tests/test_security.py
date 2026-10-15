"""Tests for password hashing and tokens (S2-07: login tests)."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import settings
from app.model.security import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)

# ---------- Passwords ----------


def test_hash_is_not_the_plain_password():
    password_hash = hash_password("correct horse battery")
    assert password_hash != "correct horse battery"
    assert password_hash.startswith("$argon2id$")  # argon2id = the recommended kind


def test_same_password_gives_different_hashes():
    # Different salt each time, so two users with the same password look different.
    assert hash_password("same") != hash_password("same")


def test_verify_accepts_right_password():
    password_hash = hash_password("correct horse battery")
    assert verify_password("correct horse battery", password_hash) is True


def test_verify_rejects_wrong_password():
    password_hash = hash_password("correct horse battery")
    assert verify_password("wrong password", password_hash) is False


def test_verify_rejects_broken_hash():
    assert verify_password("anything", "not-a-real-hash") is False


# ---------- Access tokens ----------


def test_access_token_round_trip():
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "caregiver")
    claims = decode_access_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["role"] == "caregiver"


def test_expired_token_is_rejected():
    one_minute_ago = datetime.now(UTC) - timedelta(minutes=1)
    token = jwt.encode(
        {"sub": "someone", "role": "caregiver", "exp": one_minute_ago},
        settings.jwt_secret,
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_token_signed_with_another_secret_is_rejected():
    # Someone who doesn't know our secret tries to make a token.
    in_one_hour = datetime.now(UTC) + timedelta(hours=1)
    fake = jwt.encode(
        {"sub": "attacker", "role": "admin", "exp": in_one_hour},
        "a-different-secret-that-is-at-least-32-chars-long",
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(fake)


def test_token_without_role_is_rejected():
    in_one_hour = datetime.now(UTC) + timedelta(hours=1)
    token = jwt.encode(
        {"sub": "someone", "exp": in_one_hour}, settings.jwt_secret, algorithm=JWT_ALGORITHM
    )
    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(token)


# ---------- Refresh tokens ----------


def test_refresh_tokens_are_random_and_long():
    first, second = new_refresh_token(), new_refresh_token()
    assert first != second
    assert len(first) >= 40


def test_hash_token_is_stable_and_hides_the_token():
    token = new_refresh_token()
    assert hash_token(token) == hash_token(token)  # same input → same hash (so we can look it up)
    assert hash_token(token) != token
