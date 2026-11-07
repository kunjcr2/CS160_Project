"""Tests for the settings that guard how auth starts up."""

import pytest
from pydantic import ValidationError

from app.config import Settings

# Explicit kwargs always win over .env, so these never touch the real secret.
_SOME_DATABASE_URL = "postgresql+psycopg://localhost/ignored"


def test_default_jwt_secret_is_rejected():
    with pytest.raises(ValidationError):
        Settings(database_url=_SOME_DATABASE_URL, jwt_secret="change-me-in-dotenv")


def test_short_jwt_secret_is_rejected():
    with pytest.raises(ValidationError):
        Settings(database_url=_SOME_DATABASE_URL, jwt_secret="too-short")


def test_long_random_jwt_secret_is_accepted():
    secret = "a" * 32
    settings = Settings(database_url=_SOME_DATABASE_URL, jwt_secret=secret)
    assert settings.jwt_secret == secret


def test_cookie_secure_defaults_to_true(monkeypatch):
    # conftest sets COOKIE_SECURE=false for the test suite (TestClient talks http,
    # not https); unset it here to see what a deploy with no override gets.
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    settings = Settings(database_url=_SOME_DATABASE_URL, jwt_secret="a" * 32)
    assert settings.cookie_secure is True
