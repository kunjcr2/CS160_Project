"""Tests for the per-IP rate limiter on /auth/login, /auth/register, /auth/pair."""

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from app.main import app
from app.model.rate_limit import RateLimiter, enforce_rate_limit
from app.views import messages

PASSWORD = "correct horse battery"


@pytest.fixture
def client(db):
    """A fake browser. Uses the db fixture so tables are emptied after each test."""
    return TestClient(app)


def register(client, email="rate@example.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": "Rate Test"},
    )


def login(client, email="rate@example.com", password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def pair(client):
    return client.post("/api/v1/auth/pair", json={"code": "wrong-code"})


# --- RateLimiter unit tests (no app, no HTTP): fully isolated, with a fake clock ---


class FakeClock:
    """A controllable stand-in for time.monotonic(), so tests never sleep."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_under_the_limit_is_allowed():
    clock = FakeClock()
    limiter = RateLimiter(max_attempts=5, window_seconds=60, clock=clock)
    for _ in range(5):
        limiter.check("1.2.3.4")  # does not raise


def test_exceeding_the_limit_raises_429():
    clock = FakeClock()
    limiter = RateLimiter(max_attempts=5, window_seconds=60, clock=clock)
    for _ in range(5):
        limiter.check("1.2.3.4")

    with pytest.raises(HTTPException) as excinfo:
        limiter.check("1.2.3.4")
    assert excinfo.value.status_code == 429
    assert excinfo.value.detail == messages.TOO_MANY_ATTEMPTS
    assert excinfo.value.headers["Retry-After"] == "60"


def test_limit_resets_after_the_window_elapses():
    clock = FakeClock()
    limiter = RateLimiter(max_attempts=5, window_seconds=60, clock=clock)
    for _ in range(5):
        limiter.check("1.2.3.4")

    clock.advance(61)
    limiter.check("1.2.3.4")  # does not raise: the old attempts aged out


def test_different_keys_are_tracked_separately():
    clock = FakeClock()
    limiter = RateLimiter(max_attempts=5, window_seconds=60, clock=clock)
    for _ in range(5):
        limiter.check("1.2.3.4")

    limiter.check("5.6.7.8")  # a different IP has its own, untouched count


def test_reset_clears_all_recorded_attempts():
    clock = FakeClock()
    limiter = RateLimiter(max_attempts=5, window_seconds=60, clock=clock)
    for _ in range(5):
        limiter.check("1.2.3.4")

    limiter.reset()
    limiter.check("1.2.3.4")  # does not raise: the store was cleared


# --- API tests: real HTTP requests through the three protected endpoints ---


def test_requests_under_the_limit_work_normally(client):
    for i in range(5):
        assert register(client, email=f"under{i}@example.com").status_code == 201


def test_exceeding_the_limit_returns_429(client):
    for i in range(5):
        register(client, email=f"over{i}@example.com")

    response = register(client, email="over-the-top@example.com")
    assert response.status_code == 429
    assert response.json()["detail"] == messages.TOO_MANY_ATTEMPTS
    assert "Retry-After" in response.headers


def test_rate_limit_also_applies_to_login(client):
    register(client)
    for _ in range(5):
        login(client, password="wrong password")

    assert login(client).status_code == 429


def test_rate_limit_also_applies_to_pair(client):
    for _ in range(5):
        pair(client)

    assert pair(client).status_code == 429


def test_limit_resets_after_the_window_elapses_via_api(client):
    # Swap in a limiter with a fake clock, the same way other tests swap in test
    # doubles (see app.dependency_overrides usage elsewhere), so this test never sleeps.
    clock = FakeClock()
    test_limiter = RateLimiter(max_attempts=5, window_seconds=60, clock=clock)

    def fake_enforce_rate_limit(request: Request) -> None:
        test_limiter.check(request.client.host)

    app.dependency_overrides[enforce_rate_limit] = fake_enforce_rate_limit
    try:
        for i in range(5):
            assert register(client, email=f"reset{i}@example.com").status_code == 201
        assert register(client, email="reset-blocked@example.com").status_code == 429

        clock.advance(61)  # past the window
        assert register(client, email="reset-after-window@example.com").status_code == 201
    finally:
        app.dependency_overrides.pop(enforce_rate_limit, None)
