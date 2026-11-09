"""Shared test setup. Tests use the separate voice_assistant_test database (plan §12)."""

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import dotenv_values  # installed with pydantic-settings

# Always point tests at the TEST database, never the dev one. Environment variables
# override .env in our Settings, so setting DATABASE_URL here wins.
_test_url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(".env").get("TEST_DATABASE_URL")
os.environ["DATABASE_URL"] = _test_url or "postgresql+psycopg://localhost/voice_assistant_test"
os.environ.setdefault("FAKE_AI", "true")
# TestClient talks http, not https, so a Secure cookie would never come back.
os.environ.setdefault("COOKIE_SECURE", "false")

import pytest  # noqa: E402  (must come after DATABASE_URL is set)
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.adapters.healthcare.mock import MockHealthcareProvider  # noqa: E402
from app.controllers.dependencies import get_healthcare  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.model.entities import Base, Provider, User  # noqa: E402
from app.model.security import create_access_token  # noqa: E402

LA = ZoneInfo("America/Los_Angeles")


def next_tuesday() -> date:
    """A Tuesday at least two days away (Los Angeles time), so every slot that day and
    every reminder for it is in the future."""
    day = datetime.now(LA).date() + timedelta(days=2)
    return day + timedelta(days=(1 - day.weekday()) % 7)


@pytest.fixture(scope="session")
def _schema():
    """Bring the test database up to the latest migration once per run, so the
    migrations themselves are tested. (No alembic.ini here: its logging setup would
    silence the app's loggers.)"""
    # Safety: never touch the real database by mistake.
    assert engine.url.database.endswith("_test"), "Tests must use the TEST database!"
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
    command.upgrade(config, "head")
    yield


@pytest.fixture
def db(_schema):
    """A session on the test database. Every table is emptied after the test."""
    with SessionLocal() as session:
        yield session  # the test runs here
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} CASCADE"))


@pytest.fixture
def make_user(db):
    def _make(name: str = "Margaret", timezone: str = "America/Los_Angeles") -> User:
        user = User(display_name=name, role="older_adult", timezone=timezone)
        db.add(user)
        db.commit()
        return user

    return _make


@pytest.fixture
def client(db):
    """API client. Call `client.login_as(user)` to send that user's access token."""
    test_client = TestClient(app)

    def login_as(user: User) -> None:
        token = create_access_token(user.id, user.role)
        test_client.headers["Authorization"] = f"Bearer {token}"

    test_client.login_as = login_as
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_provider():
    """A fresh mock office, so bookings don't leak between tests. The API gets it through
    the Healthcare dependency; services in tests get it passed in."""
    provider = MockHealthcareProvider()
    app.dependency_overrides[get_healthcare] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_healthcare, None)


@pytest.fixture
def chen(db) -> Provider:
    provider = Provider(
        name="Dr. Lisa Chen",
        specialty="Cardiology",
        location="Valley Medical, Building B",
        phone="408-555-0142",
        external_ref="mock-prac-cardiology-1",  # a doctor the mock office knows
    )
    db.add(provider)
    db.commit()
    return provider
