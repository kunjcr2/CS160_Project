"""Medication endpoints (PB-03): who can view, add, and answer reminders."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.model.entities import MedicationReminder, MedicationSchedule

PASSWORD = "correct horse battery"
LA = ZoneInfo("America/Los_Angeles")
METFORMIN = {
    "name": "Metformin",
    "dosage": "500 mg",
    "instructions": "Take with food",
    "schedules": [{"time_of_day": "08:00"}, {"time_of_day": "20:00"}],
}


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


def create_older_adult(client, headers, scopes):
    response = client.post(
        "/api/v1/older-adults",
        headers=headers,
        json={"display_name": "Margaret Lee", "scopes": scopes},
    )
    return response.json()["older_adult"]["id"]


def sign_in_older_adult(client, carer_headers, older_adult_id):
    """Pairing code -> the older adult's Authorization header."""
    code = client.post(
        "/api/v1/auth/pairing-codes", headers=carer_headers, json={"older_adult_id": older_adult_id}
    ).json()["code"]
    token = client.post("/api/v1/auth/pair", json={"code": code}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def carer(client):
    return sign_up(client, "carer@example.com")


@pytest.fixture
def margaret_id(client, carer):
    return create_older_adult(client, carer, ["medications:read", "medications:manage"])


@pytest.fixture
def margaret(client, carer, margaret_id):
    return sign_in_older_adult(client, carer, margaret_id)


def meds_url(older_adult_id):
    return f"/api/v1/older-adults/{older_adult_id}/medications"


def doses_url(older_adult_id):
    return f"/api/v1/older-adults/{older_adult_id}/medication-reminders"


def add_metformin(client, headers, older_adult_id):
    return client.post(meds_url(older_adult_id), headers=headers, json=METFORMIN)


def dose_due_now(db, status="sent"):
    """A dose of Margaret's Metformin that is due right now (as if the worker sent it)."""
    schedule = db.scalar(select(MedicationSchedule))
    now = datetime.now(UTC)
    dose = MedicationReminder(
        schedule_id=schedule.id,
        user_id=schedule.medication.user_id,
        due_at=now - timedelta(minutes=5),
        status=status,
        sent_at=now - timedelta(minutes=5) if status == "sent" else None,
        attempts=1 if status == "sent" else 0,
    )
    db.add(dose)
    db.commit()
    return str(dose.id)


# ---------- Adding and viewing medications ----------


def test_caregiver_adds_a_medication(client, carer, margaret_id):
    response = add_metformin(client, carer, margaret_id)
    body = response.json()
    assert response.status_code == 201
    assert body["name"] == "Metformin"
    assert [s["time_of_day"] for s in body["schedules"]] == ["08:00:00", "20:00:00"]
    assert body["schedules"][0]["days_of_week"] == [0, 1, 2, 3, 4, 5, 6]


def test_adding_creates_doses_right_away(client, carer, margaret_id):
    add_metformin(client, carer, margaret_id)
    tomorrow = (datetime.now(LA) + timedelta(days=1)).date().isoformat()
    doses = client.get(doses_url(margaret_id), headers=carer, params={"date": tomorrow}).json()
    assert [d["status"] for d in doses] == ["scheduled", "scheduled"]
    assert [d["medication_name"] for d in doses] == ["Metformin", "Metformin"]
    assert datetime.fromisoformat(doses[0]["due_at"]).astimezone(LA).hour == 8


def test_older_adult_sees_own_medications(client, carer, margaret_id, margaret):
    add_metformin(client, carer, margaret_id)
    response = client.get(meds_url(margaret_id), headers=margaret)
    assert response.status_code == 200
    assert [m["name"] for m in response.json()] == ["Metformin"]


def test_read_only_caregiver_can_view_but_not_add(client):
    carer = sign_up(client, "reader@example.com")
    older_adult_id = create_older_adult(client, carer, ["medications:read"])
    assert client.get(meds_url(older_adult_id), headers=carer).status_code == 200
    assert add_metformin(client, carer, older_adult_id).status_code == 404


def test_caregiver_without_medication_scope_gets_404(client):
    carer = sign_up(client, "appts@example.com")
    older_adult_id = create_older_adult(client, carer, ["appointments:read"])
    assert client.get(meds_url(older_adult_id), headers=carer).status_code == 404
    assert client.get(doses_url(older_adult_id), headers=carer).status_code == 404


def test_stranger_gets_404(client, margaret_id):
    stranger = sign_up(client, "stranger@example.com")
    assert client.get(meds_url(margaret_id), headers=stranger).status_code == 404
    assert add_metformin(client, stranger, margaret_id).status_code == 404


def test_not_signed_in_gets_401(client, margaret_id):
    assert client.get(meds_url(margaret_id)).status_code == 401


@pytest.mark.parametrize(
    "schedules",
    [
        [],  # no time at all
        [{"time_of_day": "08:00", "days_of_week": [7]}],  # no day 7
        [{"time_of_day": "08:00", "days_of_week": []}],  # no days
        [{"time_of_day": "08:00"}, {"time_of_day": "08:00"}],  # same time twice
    ],
    ids=["no-times", "bad-day", "no-days", "duplicate-time"],
)
def test_bad_schedule_returns_422(client, carer, margaret_id, schedules):
    response = client.post(
        meds_url(margaret_id), headers=carer, json={**METFORMIN, "schedules": schedules}
    )
    assert response.status_code == 422


# ---------- Answering a reminder ----------


def test_older_adult_marks_taken(client, db, carer, margaret_id, margaret):
    add_metformin(client, carer, margaret_id)
    dose_id = dose_due_now(db)
    response = client.post(f"/api/v1/medication-reminders/{dose_id}/taken", headers=margaret)
    assert response.status_code == 200
    assert response.json()["status"] == "taken"
    assert response.json()["confirmed_at"] is not None


def test_taken_twice_is_fine(client, db, carer, margaret_id, margaret):
    add_metformin(client, carer, margaret_id)
    dose_id = dose_due_now(db)
    url = f"/api/v1/medication-reminders/{dose_id}/taken"
    first = client.post(url, headers=margaret).json()
    second = client.post(url, headers=margaret)
    assert second.status_code == 200
    assert second.json()["confirmed_at"] == first["confirmed_at"]


def test_older_adult_marks_missed(client, db, carer, margaret_id, margaret):
    add_metformin(client, carer, margaret_id)
    dose_id = dose_due_now(db)
    response = client.post(f"/api/v1/medication-reminders/{dose_id}/missed", headers=margaret)
    assert response.json()["status"] == "missed"


def test_caregiver_cannot_answer_for_her(client, db, carer, margaret_id):
    add_metformin(client, carer, margaret_id)
    dose_id = dose_due_now(db)
    response = client.post(f"/api/v1/medication-reminders/{dose_id}/taken", headers=carer)
    assert response.status_code == 404


def test_too_early_returns_409(client, carer, margaret_id, margaret):
    add_metformin(client, carer, margaret_id)
    tomorrow = (datetime.now(LA) + timedelta(days=1)).date().isoformat()
    dose = client.get(doses_url(margaret_id), headers=margaret, params={"date": tomorrow}).json()[1]
    response = client.post(f"/api/v1/medication-reminders/{dose['id']}/taken", headers=margaret)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "too_early"


def test_cancelled_dose_returns_409(client, db, carer, margaret_id, margaret):
    add_metformin(client, carer, margaret_id)
    dose_id = dose_due_now(db, status="cancelled")
    response = client.post(f"/api/v1/medication-reminders/{dose_id}/taken", headers=margaret)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "cancelled"


def test_unknown_reminder_returns_404(client, margaret):
    url = "/api/v1/medication-reminders/00000000-0000-0000-0000-000000000000/taken"
    assert client.post(url, headers=margaret).status_code == 404
