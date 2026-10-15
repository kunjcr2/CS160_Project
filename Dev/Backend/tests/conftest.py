"""Shared test setup. Tests use the separate voice_assistant_test database."""

import os

from dotenv import dotenv_values  # installed with pydantic-settings

# Always point tests at the TEST database, never the dev one. Environment variables
# override .env in our Settings, so setting DATABASE_URL here wins.
_test_url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(".env").get("TEST_DATABASE_URL")
os.environ["DATABASE_URL"] = _test_url or "postgresql+psycopg://localhost/voice_assistant_test"
os.environ.setdefault("FAKE_AI", "true")


import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402


@pytest.fixture
def db():
    """A database session on voice_assistant_test. Empties the tables after each test."""
    from app.db import SessionLocal, engine  # imported here, after DATABASE_URL is set

    # Safety: never wipe the real database by mistake.
    assert engine.url.database.endswith("_test"), "Tests must use the TEST database!"

    with SessionLocal() as session:
        yield session  # the test runs here

    # Clean up. CASCADE also empties every table that points to these two.
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE users, providers CASCADE"))
