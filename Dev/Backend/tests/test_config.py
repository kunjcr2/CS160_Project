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
    # A real .env is free to set COOKIE_SECURE=false for local http dev, so this
    # test can't just leave the env var alone and hope .env doesn't set it. Clear
    # the env var AND stop THIS instance from reading the dotenv file at all, so
    # the result reflects only the compiled-in default, never whatever's on disk.
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    settings = Settings(database_url=_SOME_DATABASE_URL, jwt_secret="a" * 32)
    assert settings.cookie_secure is True


def test_negative_mock_provider_latency_is_rejected():
    with pytest.raises(ValidationError):
        Settings(database_url=_SOME_DATABASE_URL, jwt_secret="a" * 32, mock_provider_latency_ms=-1)


def test_mock_provider_failure_rate_must_be_between_0_and_1():
    with pytest.raises(ValidationError):
        Settings(
            database_url=_SOME_DATABASE_URL, jwt_secret="a" * 32, mock_provider_failure_rate=1.5
        )
