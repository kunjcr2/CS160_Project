from fastapi.testclient import TestClient

from app.main import app


def test_appointment_request_returns_a_typed_proposal():
    response = TestClient(app).post(
        "/api/v1/ai/process", json={"text": "Please book me with Dr. Chen next Tuesday."}
    )

    assert response.status_code == 200
    assert response.json()["proposal"] == {
        "kind": "appointment",
        "doctor": "Dr. Chen",
        "date_hint": "next tuesday",
    }


def test_medication_request_returns_a_typed_proposal_without_creating_a_reminder():
    response = TestClient(app).post(
        "/api/v1/ai/process", json={"text": "Remind me to take my aspirin at 8 pm."}
    )

    assert response.status_code == 200
    assert response.json()["proposal"] == {
        "kind": "medication_reminder",
        "medication": "aspirin",
        "time_hint": "8 pm",
    }


def test_unknown_request_does_not_propose_an_action():
    response = TestClient(app).post("/api/v1/ai/process", json={"text": "Tell me a joke."})

    assert response.status_code == 200
    assert response.json()["proposal"] is None
