"""Older adult profiles, consents, and pairing (S2-03, S2-04, S2-07)."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.model.entities import PairingCode

PASSWORD = "correct horse battery"


@pytest.fixture
def client(db):
    return TestClient(app)


def sign_up(client, email):
    """Register + log in a caregiver. Returns the Authorization header."""
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": email},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def carer(client):
    return sign_up(client, "carer@example.com")


@pytest.fixture
def margaret_id(client, carer):
    response = client.post(
        "/api/v1/older-adults",
        headers=carer,
        json={"display_name": "Margaret Lee", "scopes": ["appointments:read"]},
    )
    assert response.status_code == 201
    return response.json()["older_adult"]["id"]


def make_code(client, headers, older_adult_id):
    return client.post(
        "/api/v1/auth/pairing-codes", headers=headers, json={"older_adult_id": older_adult_id}
    )


def pair(client, code):
    return client.post("/api/v1/auth/pair", json={"code": code, "device_label": "iPad"})


# ---------- Creating a profile ----------


def test_create_older_adult_gives_caregiver_a_grant(client, carer):
    response = client.post(
        "/api/v1/older-adults",
        headers=carer,
        json={"display_name": "Margaret Lee", "scopes": ["appointments:read"]},
    )
    body = response.json()
    assert response.status_code == 201
    assert body["older_adult"]["role"] == "older_adult"
    assert body["older_adult"]["email"] is None
    assert set(body["grant"]["scopes"]) == {"appointments:read", "profile:manage"}


def test_create_with_unknown_scope_returns_422(client, carer):
    response = client.post(
        "/api/v1/older-adults",
        headers=carer,
        json={"display_name": "M", "scopes": ["conversations:read"]},
    )
    assert response.status_code == 422


def test_create_with_unknown_timezone_returns_422(client, carer):
    response = client.post(
        "/api/v1/older-adults", headers=carer, json={"display_name": "M", "timezone": "Mars/Base"}
    )
    assert response.status_code == 422


# ---------- Consents ----------


def test_list_consents_shows_my_grant(client, carer, margaret_id):
    grants = client.get("/api/v1/consents", headers=carer).json()
    assert len(grants) == 1
    assert grants[0]["older_adult_id"] == margaret_id


def test_cannot_revoke_someone_elses_grant(client, carer, margaret_id):
    grant_id = client.get("/api/v1/consents", headers=carer).json()[0]["id"]
    stranger = sign_up(client, "stranger@example.com")
    response = client.delete(f"/api/v1/consents/{grant_id}", headers=stranger)
    assert response.status_code == 404


# ---------- Pairing ----------


def test_pairing_code_signs_in_the_older_adult(client, carer, margaret_id):
    code = make_code(client, carer, margaret_id).json()["code"]
    response = pair(client, code)
    assert response.status_code == 200
    token = response.json()["access_token"]
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["id"] == margaret_id
    assert me["role"] == "older_adult"


def test_code_with_a_space_still_works(client, carer, margaret_id):
    code = make_code(client, carer, margaret_id).json()["code"]
    assert pair(client, f"{code[:4]} {code[4:]}").status_code == 200


def test_pairing_code_works_only_once(client, carer, margaret_id):
    code = make_code(client, carer, margaret_id).json()["code"]
    assert pair(client, code).status_code == 200
    assert pair(client, code).status_code == 401


def test_expired_pairing_code_fails(client, db, carer, margaret_id):
    code = make_code(client, carer, margaret_id).json()["code"]
    saved = db.scalar(select(PairingCode))
    saved.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    assert pair(client, code).status_code == 401


def test_older_adult_can_see_who_has_access(client, carer, margaret_id):
    code = make_code(client, carer, margaret_id).json()["code"]
    token = pair(client, code).json()["access_token"]
    grants = client.get("/api/v1/consents", headers={"Authorization": f"Bearer {token}"}).json()
    assert len(grants) == 1


# ---------- Permissions ----------


def test_other_caregiver_cannot_make_a_code(client, carer, margaret_id):
    stranger = sign_up(client, "stranger@example.com")
    assert make_code(client, stranger, margaret_id).status_code == 404


def test_no_code_after_grant_is_revoked(client, carer, margaret_id):
    grant_id = client.get("/api/v1/consents", headers=carer).json()[0]["id"]
    assert client.delete(f"/api/v1/consents/{grant_id}", headers=carer).status_code == 204
    assert make_code(client, carer, margaret_id).status_code == 404
