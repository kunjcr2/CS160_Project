"""API tests: real HTTP requests to our app, using the test database (S2-07)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.model.entities import Session

PASSWORD = "correct horse battery"


@pytest.fixture
def client(db):
    """A fake browser. Uses the db fixture so tables are emptied after each test."""
    return TestClient(app)


def register(client):
    return client.post(
        "/api/v1/auth/register",
        json={"email": "carer@example.com", "password": PASSWORD, "display_name": "Test Carer"},
    )


def login(client, password=PASSWORD):
    return client.post(
        "/api/v1/auth/login", json={"email": "carer@example.com", "password": password}
    )


def test_register_returns_user_without_password(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "carer@example.com"
    assert body["role"] == "caregiver"
    assert "password_hash" not in body


def test_register_twice_returns_409(client):
    register(client)
    assert register(client).status_code == 409


def test_register_with_short_password_returns_422(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "a@b.com", "password": "short", "display_name": "X"},
    )
    assert response.status_code == 422  # 422 = the JSON didn't pass the rules


def test_login_sets_httponly_refresh_cookie(client):
    register(client)
    response = login(client)
    assert response.status_code == 200
    assert response.json()["access_token"]
    cookie = response.headers["set-cookie"]
    assert "refresh_token=" in cookie
    assert "HttpOnly" in cookie


def test_login_with_wrong_password_returns_401(client):
    register(client)
    assert login(client, password="wrong password").status_code == 401


def test_me_with_token_returns_my_profile(client):
    register(client)
    token = login(client).json()["access_token"]
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "carer@example.com"


def test_me_without_token_returns_401(client):
    assert client.get("/api/v1/users/me").status_code == 401


def test_me_with_fake_token_returns_401(client):
    response = client.get("/api/v1/users/me", headers={"Authorization": "Bearer fake"})
    assert response.status_code == 401


def test_refresh_uses_the_cookie(client):
    register(client)
    login(client)  # the client keeps the cookie, like a browser
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_logout_revokes_session_and_clears_cookie(client, db):
    register(client)
    login(client)
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert db.scalar(select(Session)).revoked_at is not None  # revoked in the database
    assert client.post("/api/v1/auth/refresh").status_code == 401  # cookie is gone
