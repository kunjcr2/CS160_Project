"""Shared test setup. Tests use the separate voice_assistant_test database (plan §12)."""

import os

from dotenv import dotenv_values  # installed with pydantic-settings

# Always point tests at the TEST database, never the dev one. Environment variables
# override .env in our Settings, so setting DATABASE_URL here wins.
_test_url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(".env").get("TEST_DATABASE_URL")
os.environ["DATABASE_URL"] = _test_url or "postgresql+psycopg://localhost/voice_assistant_test"
os.environ.setdefault("FAKE_AI", "true")
