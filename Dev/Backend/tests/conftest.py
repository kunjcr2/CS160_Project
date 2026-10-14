"""Shared test setup. Tests use the separate voice_assistant_test database (plan §12)."""

import os

from dotenv import dotenv_values  # installed with pydantic-settings

# Always point tests at the TEST database, never the dev one. Environment variables
# override .env in our Settings, so setting DATABASE_URL here wins.
_test_url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(".env").get("TEST_DATABASE_URL")
os.environ["DATABASE_URL"] = _test_url or "postgresql+psycopg://localhost/voice_assistant_test"
os.environ.setdefault("FAKE_AI", "true")

import pytest  # noqa: E402  (must come after DATABASE_URL is set)
from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.controllers.dependencies import SessionDep, get_current_user  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.model.entities import Base, User  # noqa: E402


@pytest.fixture(scope="session")
def _schema():
    """Fresh tables once per test run. Built from the models until the first Alembic
    migration is merged; then switch to `alembic upgrade head` so migrations are tested."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db(_schema):
    """A session on the test database. Every table is emptied after the test."""
    session = SessionLocal()
    yield session
    session.close()
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
    """API client. Call `client.login_as(user)` to make requests as that user."""
    state = {"user_id": None}

    def _current_user(session: SessionDep) -> User:
        user = session.get(User, state["user_id"]) if state["user_id"] else None
        if user is None:
            raise HTTPException(401, "Not authenticated")
        return user

    app.dependency_overrides[get_current_user] = _current_user
    test_client = TestClient(app)
    test_client.login_as = lambda user: state.update(user_id=user.id)
    yield test_client
    app.dependency_overrides.clear()
